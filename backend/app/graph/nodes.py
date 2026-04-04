"""
Graph nodes — each function is one step in the agent pipeline.

Rules:
  - Every node receives (state, deps) and returns a partial dict
  - Nodes never mutate input state directly
  - Each node is independently testable
  - No business logic here that belongs in slot_service or commerce_handler
"""

from __future__ import annotations

import asyncio
import time

from app.api.dto.chat_dto import ChatRequest, ChatResponse, ProductCardDTO
from app.clients.llm_client import LLMClient, LLMError
from app.clients.rag_client import RAGClient
from app.clients.commerce_client import CommerceClient
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.enums.message_enums import MessageRole, GuardrailStatus
from app.db.repositories import SessionRepository, CustomerRepository, MessageRepository
from app.services.citation_service import CitationService
from app.services.commerce_handler import classify_commerce_intent
from app.services.feature_flag_service import FeatureFlagService
from app.services.guardrails_service import GuardrailsService
from app.services.memory_service import MemoryService, SlotState, ConversationHistory
from app.services.prompt_builder_service import PromptBuilderService
from app.services.rate_limiter_service import RateLimiterService
from app.services.slot_service import extract_slots, build_slot_status, enrich_tool_args, build_suggestions
from app.services.tool_registry import ToolRegistry, TOOL_DEFINITIONS
from app.services.skills.skill_registry import SkillRegistry
from app.services.skills.base_skill import SkillContext
from app.services.skills.prompts import TOOL_SELECTION_PROMPT
from app.graph.state import AgentState

settings = get_settings()
logger = get_logger(__name__)

HISTORY_TOKEN_BUDGET = 800


# ═════════════════════════════════════════════════════════════════════════════
# Dependency container — created once per request
# ═════════════════════════════════════════════════════════════════════════════

class NodeDeps:
    """All services needed by graph nodes. Created from a DB session."""

    def __init__(self, db):
        self.db = db
        self.llm = LLMClient()
        self.rag = RAGClient()
        self.rate_limiter = RateLimiterService()
        self.guardrails = GuardrailsService()
        self.memory = MemoryService(SessionRepository(db), CustomerRepository(db))
        self.prompt = PromptBuilderService()
        self.citations = CitationService()
        self.tools = ToolRegistry(self.rag)
        self.skills = SkillRegistry()
        self.commerce = CommerceClient()
        self.flags = FeatureFlagService()
        self.session_repo = SessionRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.message_repo = MessageRepository(db)


# ═════════════════════════════════════════════════════════════════════════════
# NODE 1: load_context
# ═════════════════════════════════════════════════════════════════════════════

async def load_context(state: AgentState, deps: NodeDeps) -> dict:
    """Rate limit, session resolution, load all 3 memory layers."""
    request = state["request"]

    await deps.rate_limiter.check(request.customer_id)
    session = await _resolve_session(deps, request)

    customer_profile, conversation = await asyncio.gather(
        deps.memory.load_customer_profile(session.customer_id),
        _load_history(deps, session),
    )
    slots = deps.memory.load_slots(session)
    shown_products = deps.memory.load_shown_products(session)

    if session.message_count == 0 and customer_profile:
        slots = deps.memory.prefill_slots_from_profile(slots, customer_profile)

    people = deps.memory.extract_people_from_message(request.message)

    logger.info("node.load_context", session_id=str(session.session_id))
    return {
        "session": session,
        "session_id": str(session.session_id),
        "customer_id": str(session.customer_id) if session.customer_id else None,
        "customer_profile": customer_profile,
        "conversation": conversation,
        "slots": slots,
        "shown_products": shown_products,
        "people": people,
        "input_blocked": False,
        "node_status": "Loading your profile...",
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 2: check_guardrails
# ═════════════════════════════════════════════════════════════════════════════

async def check_guardrails(state: AgentState, deps: NodeDeps) -> dict:
    """Input safety: injection, harmful content, off-topic."""
    guard = deps.guardrails.check_input(state["request"].message)
    if not guard.passed:
        logger.warning("node.guardrails_blocked", reason=guard.reason)
        return {
            "input_blocked": True,
            "block_response": guard.safe_response or "I can only help with shopping.",
            "guard_status": "BLOCKED",
        }
    return {"input_blocked": False, "guard_status": "PASSED"}


# ═════════════════════════════════════════════════════════════════════════════
# NODE 3: extract_intent
# ═════════════════════════════════════════════════════════════════════════════

async def extract_intent(state: AgentState, deps: NodeDeps) -> dict:
    """Keyword-based intent + regex slot extraction. Zero LLM cost."""
    message = state["request"].message
    intent = deps.guardrails.classify_intent(message)
    slots = extract_slots(message, state["slots"])
    commerce = classify_commerce_intent(message)

    logger.info("node.extract_intent", intent=intent, commerce=commerce)
    return {
        "intent": intent,
        "slots": slots,
        "commerce_intent": commerce,
        "node_status": "Understanding your request...",
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 4: activate_skills
# ═════════════════════════════════════════════════════════════════════════════

async def activate_skills(state: AgentState, deps: NodeDeps) -> dict:
    """Evaluate 5 skills in priority order, merge prompts."""
    ctx = SkillContext(
        message=state["request"].message,
        intent=state["intent"],
        slots=state["slots"],
        customer_profile=state["customer_profile"],
        session_context=state["session"].context or {},
        turn_count=state["session"].message_count,
    )
    result = deps.skills.resolve(ctx)
    active = result.metadata.get("active_skills", [])
    if active:
        logger.info("node.skills_active", skills=active)
    return {
        "skill_prompt_addon": result.prompt_addon or "",
        "skill_extra_tools": result.extra_tools,
        "active_skills": active,
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 5: decide_tool — 1st GPT-4o call
# ═════════════════════════════════════════════════════════════════════════════

async def decide_tool(state: AgentState, deps: NodeDeps) -> dict:
    """LLM decides which tool to invoke based on slots + skills."""
    request = state["request"]
    slots = state["slots"]

    slot_status = build_slot_status(slots)
    prompt = TOOL_SELECTION_PROMPT + "\n\n" + slot_status
    if state.get("skill_prompt_addon"):
        prompt += "\n\n" + state["skill_prompt_addon"]

    tools = TOOL_DEFINITIONS + (state.get("skill_extra_tools") or [])
    history = _trim_history(state["conversation"])

    try:
        tool_call = await deps.llm.decide_tool(
            system_prompt=prompt,
            user_message=request.message,
            history=history,
            tools=tools,
            image_base64=getattr(request, "image_base64", None),
        )
    except LLMError as e:
        logger.error("node.decide_tool_failed", error=str(e))
        return {"tool_name": "error", "tool_args": {}, "llm_history": history, "error": str(e)}

    args = enrich_tool_args(tool_call.tool_name, tool_call.tool_args, slots, request.filters)
    logger.info("node.decide_tool", tool=tool_call.tool_name)

    return {
        "tool_call": tool_call,
        "tool_name": tool_call.tool_name,
        "tool_args": args,
        "llm_history": history,
        "node_status": "Analyzing your request...",
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 6: execute_tool
# ═════════════════════════════════════════════════════════════════════════════

async def execute_tool(state: AgentState, deps: NodeDeps) -> dict:
    """Run the selected tool (RAG search, compare, outfit, etc.)"""
    tool_name = state["tool_name"]
    logger.info("node.execute_tool", tool=tool_name)

    status_map = {
        "search_products": "Searching products...",
        "compare_products": "Comparing products...",
        "outfit_pairing": "Finding matching shoes...",
        "gift_finder": "Finding gift ideas...",
        "size_advice": "Checking sizing info...",
        "stock_check": "Checking availability...",
        "clarify_question": "Thinking...",
        "direct_answer": "Thinking...",
    }

    result = await deps.tools.execute(tool_name, state["tool_args"])
    return {
        "tool_result": result,
        "node_status": status_map.get(tool_name, "Processing..."),
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 7: generate_response — 2nd GPT-4o call
# ═════════════════════════════════════════════════════════════════════════════

async def generate_response(state: AgentState, deps: NodeDeps) -> dict:
    """Generate natural language response using tool results + context."""
    request = state["request"]
    tool_name = state["tool_name"]
    tool_result = state.get("tool_result")

    # Build tool summary
    if tool_name == "clarify_question":
        summary = state["tool_args"].get("question", "Could you tell me more?")
    elif tool_name == "direct_answer":
        summary = state["tool_args"].get("content", "")
    else:
        summary = tool_result.summary if tool_result else ""

    # Build prompt with all memory layers
    system_prompt, _, citation_map = deps.prompt.build(
        user_message=request.message,
        history=state["conversation"],
        retrieved_chunks=tool_result.retrieved_chunks if tool_result else [],
        slots=state["slots"],
        customer_profile=state["customer_profile"],
        shown_products=state["shown_products"],
        tool_context=summary,
    )

    try:
        llm_result = await deps.llm.generate(
            system_prompt=system_prompt,
            user_message=request.message,
            history=state["llm_history"],
            tool_result_summary=summary,
            tool_name=tool_name,
            image_base64=getattr(request, "image_base64", None),
        )
    except LLMError as e:
        logger.error("node.generate_failed", error=str(e))
        return {
            "llm_result": None,
            "system_prompt": system_prompt,
            "citation_map": citation_map,
            "error": str(e),
        }

    logger.info("node.generate_response", tokens=llm_result.input_tokens + llm_result.output_tokens)
    return {
        "llm_result": llm_result,
        "system_prompt": system_prompt,
        "citation_map": citation_map,
        "node_status": "Writing response...",
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 8: process_output
# ═════════════════════════════════════════════════════════════════════════════

async def process_output(state: AgentState, deps: NodeDeps) -> dict:
    """Output guardrails + citation processing."""
    llm_result = state.get("llm_result")
    tool_result = state.get("tool_result")
    citation_map = state.get("citation_map", {})

    if not llm_result:
        return {
            "answer": "Something went wrong. Please try again.",
            "answer_html": "Something went wrong. Please try again.",
            "cited_products": [],
            "suggestions": [],
            "guard_status": "PASSED",
        }

    raw = llm_result.content
    retrieved_ids = [c.product_id for c in tool_result.retrieved_chunks] if tool_result else []
    out_guard = deps.guardrails.check_output(raw, retrieved_ids)

    final_text = raw
    guard_status = "PASSED"
    if not out_guard.passed:
        final_text = out_guard.safe_response or raw
        guard_status = "WARNED"

    answer, answer_html, cited = deps.citations.process(final_text, citation_map)
    suggestions = build_suggestions(llm_result.suggestions)

    logger.info("node.process_output", citations=len(cited), guard=guard_status)
    return {
        "answer": answer,
        "answer_html": answer_html,
        "cited_products": cited,
        "suggestions": suggestions,
        "guard_status": guard_status,
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 9: persist
# ═════════════════════════════════════════════════════════════════════════════

async def persist(state: AgentState, deps: NodeDeps) -> dict:
    """Save messages to DB, update session memory, build ChatResponse."""
    request = state["request"]
    session = state["session"]
    llm_result = state.get("llm_result")
    t_start = state["t_start"]
    intent = state.get("intent", "unknown")

    # Blocked response
    if state.get("input_blocked"):
        answer = state.get("block_response", "I can only help with shopping.")
        await _persist_turn(deps, session, request.message, answer, "blocked", GuardrailStatus.BLOCKED)
        return {"response": _build_response(session, answer, answer, [], [], "blocked", True, t_start, 0)}

    # Error response
    if state.get("error") and not state.get("answer"):
        answer = "Oops, something went wrong. Please try again."
        await _persist_turn(deps, session, request.message, answer, intent, GuardrailStatus.PASSED)
        return {"response": _build_response(session, answer, answer, [], [], intent, False, t_start, 0)}

    # Normal response
    answer = state.get("answer", "")
    answer_html = state.get("answer_html", answer)
    cited = state.get("cited_products", [])
    suggestions = state.get("suggestions", [])
    guard = GuardrailStatus.WARNED if state.get("guard_status") == "WARNED" else GuardrailStatus.PASSED

    input_tokens = llm_result.input_tokens if llm_result else 0
    output_tokens = llm_result.output_tokens if llm_result else 0
    total_tokens = input_tokens + output_tokens

    # Persist user + bot messages
    await deps.message_repo.create(
        session_id=session.session_id, role=MessageRole.USER,
        content=request.message, intent=intent,
        guardrail_status=GuardrailStatus.PASSED,
    )
    bot_msg = await deps.message_repo.create(
        session_id=session.session_id, role=MessageRole.ASSISTANT,
        content=answer, intent=intent, guardrail_status=guard,
        cited_products=[p.model_dump() for p in cited] if cited else [],
        input_tokens=input_tokens, output_tokens=output_tokens,
        latency_ms=int((time.monotonic() - t_start) * 1000),
        llm_model=llm_result.model if llm_result else "unknown",
    )

    await deps.session_repo.increment_counters(session.session_id, turn_delta=2, token_delta=total_tokens)

    if state.get("slots"):
        await deps.memory.persist_session_memory(
            session=session, slots=state["slots"],
            cited_products=cited or [], intent=intent,
        )

    await deps.db.commit()

    # Schedule background tasks
    _schedule_background(deps, session, state)

    latency = int((time.monotonic() - t_start) * 1000)
    logger.info("node.persist", session_id=str(session.session_id), latency_ms=latency, tokens=total_tokens)

    return {
        "response": ChatResponse(
            message_id=bot_msg.message_id,
            session_id=session.session_id,
            answer=answer, answer_html=answer_html,
            cited_products=cited or [],
            suggestions=suggestions,
            intent=intent,
            guardrail_status=guard,
            blocked=False,
            latency_ms=latency,
            tokens_used=total_tokens,
        )
    }


# ═════════════════════════════════════════════════════════════════════════════
# Helpers (private, not nodes)
# ═════════════════════════════════════════════════════════════════════════════

async def _resolve_session(deps: NodeDeps, request: ChatRequest):
    if request.customer_id:
        session, _ = await deps.session_repo.get_or_create(
            customer_id=request.customer_id, channel=request.channel,
        )
        return session
    return await deps.session_repo.create(
        customer_id=request.customer_id, channel=request.channel,
    )


async def _load_history(deps: NodeDeps, session) -> ConversationHistory:
    messages = await deps.message_repo.get_recent_turns(session_id=session.session_id, limit=10)
    turns = [
        {"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content}
        for m in messages
    ]
    summary = deps.memory.load_summary(session)
    return ConversationHistory(recent_turns=turns, summary=summary)


def _trim_history(conversation: ConversationHistory) -> list[dict]:
    max_turns, min_turns, budget = 6, 2, HISTORY_TOKEN_BUDGET
    candidates = conversation.recent_turns[-max_turns:]
    result: list[dict] = []
    token_sum = 0
    for turn in reversed(candidates):
        est = len(turn["content"]) // 4
        if result and len(result) >= min_turns and token_sum + est > budget:
            break
        result.append({"role": turn["role"], "content": turn["content"]})
        token_sum += est
    result.reverse()
    return result


async def _persist_turn(deps, session, user_msg, bot_msg, intent, guard_status):
    await deps.message_repo.create(
        session_id=session.session_id, role=MessageRole.USER,
        content=user_msg, intent=intent, guardrail_status=guard_status,
    )
    msg = await deps.message_repo.create(
        session_id=session.session_id, role=MessageRole.ASSISTANT,
        content=bot_msg, intent=intent, guardrail_status=guard_status,
    )
    await deps.session_repo.increment_counters(session.session_id, turn_delta=2)
    await deps.db.commit()
    return msg


def _build_response(session, answer, html, cited, suggestions, intent, blocked, t_start, tokens):
    return ChatResponse(
        message_id=str(session.session_id),
        session_id=session.session_id,
        answer=answer, answer_html=html,
        cited_products=cited, suggestions=suggestions,
        intent=intent,
        guardrail_status=GuardrailStatus.BLOCKED if blocked else GuardrailStatus.PASSED,
        blocked=blocked,
        latency_ms=int((time.monotonic() - t_start) * 1000),
        tokens_used=tokens,
    )


def _schedule_background(deps: NodeDeps, session, state: AgentState):
    """Fire-and-forget profile update + summarization."""
    import asyncio as _aio

    async def _bg_update():
        try:
            await deps.memory.update_customer_profile(
                customer_id=session.customer_id,
                slots=state.get("slots"),
                cited_products=state.get("cited_products", []),
                intent=state.get("intent", ""),
                people=state.get("people", []),
            )
        except Exception as e:
            logger.warning("bg.profile_update_failed", error=str(e))

    if session.customer_id:
        _aio.get_event_loop().create_task(_bg_update())
