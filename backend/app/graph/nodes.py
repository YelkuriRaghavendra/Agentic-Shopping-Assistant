"""
Graph nodes — each function is one step in the agent pipeline.

Every node:
  - Receives the full AgentState
  - Returns a partial dict with ONLY the keys it updates
  - Never mutates the input state directly
  - Is independently testable
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.api.dto.chat_dto import ChatRequest, ChatResponse, ProductCardDTO
from app.clients.llm_client import LLMClient, ToolCall, LLMError
from app.clients.rag_client import RAGClient
from app.clients.commerce_client import CommerceClient
from app.config.loader import business_rules, prompts
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.enums.message_enums import MessageRole, GuardrailStatus
from app.db.repositories import SessionRepository, CustomerRepository, MessageRepository
from app.services.citation_service import CitationService
from app.services.feature_flag_service import FeatureFlagService
from app.services.guardrails_service import GuardrailsService
from app.services.memory_service import MemoryService, SlotState, ConversationHistory
from app.services.prompt_builder_service import PromptBuilderService
from app.services.rate_limiter_service import RateLimiterService
from app.services.tool_registry import ToolRegistry, TOOL_DEFINITIONS, ToolResult
from app.services.skills.skill_registry import SkillRegistry
from app.services.skills.base_skill import SkillContext
from app.services.skills.prompts import TOOL_SELECTION_PROMPT
from app.graph.state import AgentState

settings = get_settings()
logger = get_logger(__name__)

HISTORY_TOKEN_BUDGET = 800


class NodeDeps:
    """
    Shared dependencies injected into every node.
    Created once per request from the DB session.
    """

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession

        self.db = db
        self.llm = LLMClient()
        self.rag = RAGClient()
        self.rate_limiter = RateLimiterService(db)
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
# NODE 1: Load Context
# ═════════════════════════════════════════════════════════════════════════════

async def load_context(state: AgentState, deps: NodeDeps) -> dict:
    """
    Rate limit check, session resolution, load all memory layers.
    This is the entry point — sets up everything the pipeline needs.
    """
    request = state["request"]
    t_start = state["t_start"]

    # Rate limit
    await deps.rate_limiter.check(request.customer_id)

    # Resolve session
    session = await _resolve_session(deps, request)

    # Load memory layers in parallel
    customer_profile, conversation = await asyncio.gather(
        deps.memory.load_customer_profile(session.customer_id),
        _load_history(deps, session),
    )
    slots = deps.memory.load_slots(session)
    shown_products = deps.memory.load_shown_products(session)

    # Pre-fill slots for returning customers
    if session.message_count == 0 and customer_profile:
        slots = deps.memory.prefill_slots_from_profile(slots, customer_profile)

    # Extract people mentions for cross-session memory
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
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 2: Input Guardrails
# ═════════════════════════════════════════════════════════════════════════════

async def check_guardrails(state: AgentState, deps: NodeDeps) -> dict:
    """
    Check input for prompt injection, harmful content, off-topic.
    If blocked, sets input_blocked=True and the graph routes to persist.
    """
    request = state["request"]
    guard = deps.guardrails.check_input(request.message)

    if not guard.passed:
        logger.warning("node.guardrails_blocked", reason=guard.reason)
        return {
            "input_blocked": True,
            "block_reason": guard.reason or "blocked",
            "block_response": guard.safe_response or "I can only help with shopping-related questions.",
            "guard_status": "BLOCKED",
        }

    return {
        "input_blocked": False,
        "guard_status": "PASSED",
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 3: Extract Intent + Slots
# ═════════════════════════════════════════════════════════════════════════════

async def extract_intent(state: AgentState, deps: NodeDeps) -> dict:
    """
    Keyword-based intent classification + regex slot extraction.
    Zero LLM cost — pure pattern matching.
    """
    from app.services.chat_service import _classify_commerce_intent

    request = state["request"]
    slots = state["slots"]

    intent = deps.guardrails.classify_intent(request.message)

    # Use ChatService's slot extraction (static method pattern)
    from app.services.chat_service import ChatService
    svc = ChatService.__new__(ChatService)
    slots = svc._extract_slots(request.message, slots)

    commerce_intent = _classify_commerce_intent(request.message)

    logger.info("node.extract_intent", intent=intent, commerce=commerce_intent)

    return {
        "intent": intent,
        "slots": slots,
        "commerce_intent": commerce_intent,
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 4: Activate Skills
# ═════════════════════════════════════════════════════════════════════════════

async def activate_skills(state: AgentState, deps: NodeDeps) -> dict:
    """
    Evaluate 5 skills in priority order, merge active prompts.
    """
    skill_ctx = SkillContext(
        message=state["request"].message,
        intent=state["intent"],
        slots=state["slots"],
        customer_profile=state["customer_profile"],
        session_context=state["session"].context or {},
        turn_count=state["session"].message_count,
    )
    result = deps.skills.resolve(skill_ctx)

    active = result.metadata.get("active_skills", [])
    if active:
        logger.info("node.skills_active", skills=active)

    return {
        "skill_prompt_addon": result.prompt_addon or "",
        "skill_extra_tools": result.extra_tools,
        "active_skills": active,
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 5: LLM Tool Decision (1st GPT-4o call)
# ═════════════════════════════════════════════════════════════════════════════

async def decide_tool(state: AgentState, deps: NodeDeps) -> dict:
    """
    First LLM call. GPT-4o reads the conversation + slot status
    and decides which tool to invoke.
    """
    from app.services.chat_service import ChatService

    request = state["request"]
    slots = state["slots"]
    conversation = state["conversation"]

    # Build tool selection prompt with slot status
    svc = ChatService.__new__(ChatService)  # borrow static method
    slot_status = svc._build_slot_status(slots)
    tool_system_prompt = TOOL_SELECTION_PROMPT + "\n\n" + slot_status
    if state.get("skill_prompt_addon"):
        tool_system_prompt += "\n\n" + state["skill_prompt_addon"]

    active_tools = TOOL_DEFINITIONS + (state.get("skill_extra_tools") or [])

    # Token-budget-aware history trimming
    llm_history = _trim_history(conversation)

    try:
        tool_call = await deps.llm.decide_tool(
            system_prompt=tool_system_prompt,
            user_message=request.message,
            history=llm_history,
            tools=active_tools,
            image_base64=getattr(request, "image_base64", None),
        )
    except LLMError as e:
        logger.error("node.decide_tool_failed", error=str(e))
        return {
            "tool_call": None,
            "tool_name": "error",
            "tool_args": {},
            "llm_history": llm_history,
            "error": "LLM failed to decide tool",
        }

    # Enrich tool args with slot values
    tool_args = svc._enrich_tool_args(
        tool_call.tool_name, tool_call.tool_args, slots, request.filters
    )

    logger.info("node.decide_tool", tool=tool_call.tool_name)

    return {
        "tool_call": tool_call,
        "tool_name": tool_call.tool_name,
        "tool_args": tool_args,
        "llm_history": llm_history,
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 6: Execute Tool
# ═════════════════════════════════════════════════════════════════════════════

async def execute_tool(state: AgentState, deps: NodeDeps) -> dict:
    """
    Run the selected tool (RAG search, compare, outfit pairing, etc.)
    """
    tool_name = state["tool_name"]
    tool_args = state["tool_args"]

    logger.info("node.execute_tool", tool=tool_name)

    tool_result = await deps.tools.execute(tool_name, tool_args)

    return {
        "tool_result": tool_result,
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 7: Generate Response (2nd GPT-4o call)
# ═════════════════════════════════════════════════════════════════════════════

async def generate_response(state: AgentState, deps: NodeDeps) -> dict:
    """
    Second LLM call. Takes tool results + context, generates
    a natural language response with product citations.
    """
    request = state["request"]
    tool_name = state["tool_name"]
    tool_result = state.get("tool_result")
    conversation = state["conversation"]
    slots = state["slots"]
    customer_profile = state["customer_profile"]
    shown_products = state["shown_products"]
    llm_history = state["llm_history"]

    # For clarify/direct tools, the "result" is the tool args content
    if tool_name == "clarify_question":
        tool_summary = state["tool_args"].get("question", "Could you tell me more?")
    elif tool_name == "direct_answer":
        tool_summary = state["tool_args"].get("content", "")
    else:
        tool_summary = tool_result.summary if tool_result else ""

    # Build prompt with all context layers
    system_prompt, _, citation_map = deps.prompt.build(
        user_message=request.message,
        history=conversation,
        retrieved_chunks=tool_result.retrieved_chunks if tool_result else [],
        slots=slots,
        customer_profile=customer_profile,
        shown_products=shown_products,
        tool_context=tool_summary,
    )

    try:
        llm_result = await deps.llm.generate(
            system_prompt=system_prompt,
            user_message=request.message,
            history=llm_history,
            tool_result_summary=tool_summary,
            tool_name=tool_name,
            image_base64=getattr(request, "image_base64", None),
        )
    except LLMError as e:
        logger.error("node.generate_failed", error=str(e))
        return {
            "llm_result": None,
            "raw_response": "I'm having trouble responding right now. Please try again.",
            "system_prompt": system_prompt,
            "citation_map": citation_map,
            "error": str(e),
        }

    logger.info("node.generate_response", tokens=llm_result.input_tokens + llm_result.output_tokens)

    return {
        "llm_result": llm_result,
        "raw_response": llm_result.content,
        "system_prompt": system_prompt,
        "citation_map": citation_map,
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 8: Process Output (Guardrails + Citations)
# ═════════════════════════════════════════════════════════════════════════════

async def process_output(state: AgentState, deps: NodeDeps) -> dict:
    """
    Output guardrails (hallucination check) + citation processing
    ([P1][P2] → product cards + HTML).
    """
    raw_response = state.get("raw_response", "")
    citation_map = state.get("citation_map", {})
    tool_result = state.get("tool_result")
    llm_result = state.get("llm_result")

    # Output guardrails
    retrieved_ids = [c.product_id for c in tool_result.retrieved_chunks] if tool_result else []
    out_guard = deps.guardrails.check_output(raw_response, retrieved_ids)

    final_text = raw_response
    guard_status = "PASSED"
    if not out_guard.passed:
        final_text = out_guard.safe_response or final_text
        guard_status = "WARNED"

    # Citation processing
    answer, answer_html, cited_products = deps.citations.process(final_text, citation_map)

    # Build suggestions
    suggestions = []
    if llm_result and llm_result.suggestions:
        suggestions = [
            {"label": s.label[:40], "message": s.message}
            for s in llm_result.suggestions
            if s.label
        ][:4]

    logger.info("node.process_output", citations=len(cited_products), guard=guard_status)

    return {
        "answer": answer,
        "answer_html": answer_html,
        "cited_products": cited_products,
        "suggestions": suggestions,
        "final_guard_status": guard_status,
    }


# ═════════════════════════════════════════════════════════════════════════════
# NODE 9: Persist + Build Response
# ═════════════════════════════════════════════════════════════════════════════

async def persist(state: AgentState, deps: NodeDeps) -> dict:
    """
    Save messages to DB, update session memory, build final ChatResponse.
    """
    request = state["request"]
    session = state["session"]
    intent = state.get("intent", "unknown")
    slots = state.get("slots")
    cited_products = state.get("cited_products", [])
    llm_result = state.get("llm_result")
    t_start = state["t_start"]
    people = state.get("people", [])

    # Handle blocked responses
    if state.get("input_blocked"):
        answer = state.get("block_response", "I can only help with shopping.")
        await deps.message_repo.create(
            session_id=session.session_id, role=MessageRole.USER,
            content=request.message, intent="blocked",
            guardrail_status=GuardrailStatus.BLOCKED,
        )
        bot_msg = await deps.message_repo.create(
            session_id=session.session_id, role=MessageRole.ASSISTANT,
            content=answer, intent="blocked",
            guardrail_status=GuardrailStatus.BLOCKED,
        )
        await deps.session_repo.increment_counters(session.session_id, turn_delta=2)
        await deps.db.commit()
        return {
            "response": ChatResponse(
                message_id=bot_msg.message_id, session_id=session.session_id,
                answer=answer, answer_html=answer, cited_products=[],
                suggestions=[], intent="blocked",
                guardrail_status=GuardrailStatus.BLOCKED, blocked=True,
                latency_ms=int((time.monotonic() - t_start) * 1000), tokens_used=0,
            )
        }

    # Handle errors
    if state.get("error") and not state.get("answer"):
        answer = "Oops, something went wrong. Please try again."
        await deps.message_repo.create(
            session_id=session.session_id, role=MessageRole.USER,
            content=request.message, intent=intent,
            guardrail_status=GuardrailStatus.PASSED,
        )
        bot_msg = await deps.message_repo.create(
            session_id=session.session_id, role=MessageRole.ASSISTANT,
            content=answer, intent=intent,
            guardrail_status=GuardrailStatus.PASSED,
        )
        await deps.session_repo.increment_counters(session.session_id, turn_delta=2)
        await deps.db.commit()
        return {
            "response": ChatResponse(
                message_id=bot_msg.message_id, session_id=session.session_id,
                answer=answer, answer_html=answer, cited_products=[],
                suggestions=[], intent=intent,
                guardrail_status=GuardrailStatus.PASSED, blocked=False,
                latency_ms=int((time.monotonic() - t_start) * 1000), tokens_used=0,
            )
        }

    # Normal response
    answer = state.get("answer", "")
    answer_html = state.get("answer_html", answer)
    guard_status_str = state.get("final_guard_status", "PASSED")
    guard_status = GuardrailStatus.WARNED if guard_status_str == "WARNED" else GuardrailStatus.PASSED

    input_tokens = llm_result.input_tokens if llm_result else 0
    output_tokens = llm_result.output_tokens if llm_result else 0

    # Persist user message
    await deps.message_repo.create(
        session_id=session.session_id, role=MessageRole.USER,
        content=request.message, intent=intent,
        guardrail_status=GuardrailStatus.PASSED,
    )

    # Persist bot message
    bot_msg = await deps.message_repo.create(
        session_id=session.session_id, role=MessageRole.ASSISTANT,
        content=answer, intent=intent, guardrail_status=guard_status,
        cited_products=[p.model_dump() for p in cited_products] if cited_products else [],
        input_tokens=input_tokens, output_tokens=output_tokens,
        latency_ms=int((time.monotonic() - t_start) * 1000),
        llm_model=llm_result.model if llm_result else "unknown",
    )

    # Update session counters
    await deps.session_repo.increment_counters(
        session_id=session.session_id,
        turn_delta=2,
        token_delta=input_tokens + output_tokens,
    )

    # Persist memory
    if slots:
        await deps.memory.persist_session_memory(
            session=session, slots=slots,
            cited_products=cited_products or [], intent=intent,
        )

    await deps.db.commit()

    latency_ms = int((time.monotonic() - t_start) * 1000)
    logger.info(
        "node.persist",
        session_id=str(session.session_id),
        tool=state.get("tool_name", "unknown"),
        latency_ms=latency_ms,
        tokens=input_tokens + output_tokens,
    )

    return {
        "response": ChatResponse(
            message_id=bot_msg.message_id,
            session_id=session.session_id,
            answer=answer,
            answer_html=answer_html,
            cited_products=cited_products or [],
            suggestions=state.get("suggestions", []),
            intent=intent,
            guardrail_status=guard_status,
            blocked=False,
            latency_ms=latency_ms,
            tokens_used=input_tokens + output_tokens,
        )
    }


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

async def _resolve_session(deps: NodeDeps, request: ChatRequest):
    """Find active session or create a new one."""
    if request.session_id:
        session = await deps.session_repo.get(request.session_id)
        if session:
            return session
    if request.customer_id:
        session, _ = await deps.session_repo.get_or_create(
            customer_id=request.customer_id,
            channel=request.channel,
        )
        return session
    session = await deps.session_repo.create(
        customer_id=request.customer_id,
        channel=request.channel,
    )
    return session


async def _load_history(deps: NodeDeps, session) -> ConversationHistory:
    """Load recent conversation turns from DB."""
    messages = await deps.message_repo.get_recent_turns(
        session_id=session.session_id, limit=10,
    )
    recent_turns = [
        {"role": m.role.value if hasattr(m.role, "value") else m.role, "content": m.content}
        for m in messages
    ]
    summary = deps.memory.load_summary(session)
    return ConversationHistory(recent_turns=recent_turns, summary=summary)


def _trim_history(conversation: ConversationHistory) -> list[dict]:
    """Token-budget-aware history trimming."""
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
