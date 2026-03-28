"""
Chat service — main orchestrator.

Single responsibility: coordinate all other services to handle
one customer message and produce a ChatResponse.

Flow:
  1.  Auto-resolve session (find active or create new)
  2.  Rate limit check
  3.  Session health check (expired? token budget exceeded?)
  4.  Load memory (customer profile + session context)
  5.  Input guardrails
  6.  Classify intent
  7.  Extract + update slots
  8.  Commerce intent routing (feature-flag gated)
  9.  LLM decides which tool to call
  10. Execute tool (RAG, order lookup, policy, etc.)
  11. Build prompt (all memory layers injected)
  12. Generate LLM response
  13. Output guardrails
  14. Citation processing
  15. Persist messages + update memory
  16. Trigger background tasks (profile update, summarisation)
  17. Return structured response

This service knows nothing about HTTP — no FastAPI, no Request, no Response.
"""

import asyncio
import json
import re
import time
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dto.chat_dto import ChatRequest, ChatResponse, ProductCardDTO
from app.clients.llm_client import LLMClient, ToolCall, SuggestionItem
from app.clients.rag_client import RAGClient
from app.clients.commerce_client import CommerceClient
from app.config.loader import business_rules, prompts
from app.core.config import get_settings
from app.core.exceptions import (
    SessionNotFoundError,
    SessionExpiredError,
    SessionInactiveError,
    TokenBudgetExceededError,
    LLMError,
)
from app.db.models.session import Session
from app.db.models.enums.session_enums import SessionStatus
from app.db.models.enums.message_enums import MessageRole, GuardrailStatus
from app.db.repositories import (
    SessionRepository,
    CustomerRepository,
    MessageRepository,
)
from app.services.citation_service import CitationService
from app.services.feature_flag_service import FeatureFlagService, COMMERCE_INTENTS
from app.services.guardrails_service import GuardrailsService
from app.services.memory_service import MemoryService, SlotState, ConversationHistory, PersonNote
from app.services.prompt_builder_service import PromptBuilderService
from app.services.rate_limiter_service import RateLimiterService
from app.services.tool_registry import ToolRegistry, TOOL_DEFINITIONS
from app.services.skills.skill_registry import SkillRegistry
from app.services.skills.base_skill import SkillContext
from app.services.skills.prompts import TOOL_SELECTION_PROMPT
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Max estimated tokens to spend on conversation history sent to the LLM.
# Each turn's token count is approximated as len(content) // 4.
HISTORY_TOKEN_BUDGET = 800

# LLM prompt that teaches the agent when to ask vs when to search
# Tool selection prompt lives in app/services/skills/prompts.py → TOOL_SELECTION_PROMPT


# ─────────────────────────────────────────────────────────────────────────────
# Commerce intent classification
# ─────────────────────────────────────────────────────────────────────────────

# Keyword → commerce intent mapping (evaluated before LLM tool-calling)
_COMMERCE_INTENT_MAP: list[tuple[list[str], str]] = [
    (["checkout", "check out", "place order", "place my order", "buy now", "proceed to checkout"], "checkout_initiate"),
    (["add to cart", "add to my cart", "put in cart", "put it in", "add it", "add this"], "add_to_cart"),
    (["remove from cart", "take out of cart", "delete from cart", "remove it", "take it out"], "remove_from_cart"),
    (["view cart", "show cart", "what's in my cart", "my cart", "see my cart", "show my cart"], "view_cart"),
    (["order status", "where is my order", "track my order", "order #", "order number"], "order_status"),
    (["order history", "my orders", "past orders", "previous orders", "all orders", "show my orders"], "order_history"),
    (["cancel order", "cancel my order", "cancel purchase"], "cancel_order"),
]

# Required slots per commerce intent
_REQUIRED_SLOTS: dict[str, list[str]] = {
    "add_to_cart":       ["product_id", "quantity"],
    "remove_from_cart":  ["product_id"],
    "view_cart":         [],
    "checkout_initiate": ["line_items"],
    "order_status":      ["order_id"],
    "order_history":     [],
    "cancel_order":      ["order_id"],
}

# Re-prompt questions for missing slots
_SLOT_PROMPTS: dict[str, str] = {
    "product_id":  "Which product would you like? Could you describe it or give me the product name?",
    "quantity":    "How many would you like to add?",
    "order_id":    "Could you share your order number? You can find it in your confirmation email.",
    "line_items":  "Your cart appears to be empty. Would you like to add some items first?",
}


def _classify_commerce_intent(message: str) -> str | None:
    """
    Keyword-based commerce intent classifier.
    Returns a commerce intent name or None if no match.
    Zero LLM cost.
    """
    msg = message.lower()
    for keywords, intent in _COMMERCE_INTENT_MAP:
        if any(kw in msg for kw in keywords):
            return intent
    return None


class ChatService:
    """
    All dependencies are injected — makes testing easy.
    Never instantiate this directly — use the factory function below.
    """

    def __init__(
        self,
        db:            AsyncSession,
        llm_client:    LLMClient,
        rag_client:    RAGClient,
        rate_limiter:  RateLimiterService,
        guardrails:    GuardrailsService,
        memory:        MemoryService,
        prompt:        PromptBuilderService,
        citations:     CitationService,
        tools:         ToolRegistry,
        skills:        SkillRegistry,
        commerce:      CommerceClient | None = None,
        feature_flags: FeatureFlagService | None = None,
    ):
        self._db           = db
        self._llm          = llm_client
        self._rag          = rag_client
        self._rate_limiter = rate_limiter
        self._guardrails   = guardrails
        self._memory       = memory
        self._prompt       = prompt
        self._citations    = citations
        self._tools        = tools
        self._skills       = skills
        self._commerce     = commerce or CommerceClient()
        self._flags        = feature_flags or FeatureFlagService()

        self._session_repo  = SessionRepository(db)
        self._customer_repo = CustomerRepository(db)
        self._message_repo  = MessageRepository(db)

    async def handle(self, request: ChatRequest) -> ChatResponse:
        t_start = time.monotonic()

        # ── 1. Rate limit ─────────────────────────────────────────────────
        await self._rate_limiter.check(request.customer_id)

        # ── 2. Resolve session ────────────────────────────────────────────
        session = await self._resolve_session(request)

        # ── 3. Session health ─────────────────────────────────────────────
        await self._check_session_health(session)

        # ── 4. Load memory (async calls run in parallel) ─────────────────
        customer_profile, conversation = await asyncio.gather(
            self._memory.load_customer_profile(session.customer_id),
            self._load_history(session),
        )
        slots          = self._memory.load_slots(session)
        shown_products = self._memory.load_shown_products(session)

        # Pre-fill slots for returning customers (skip questions they answered before)
        if session.message_count == 0 and customer_profile:
            slots = self._memory.prefill_slots_from_profile(slots, customer_profile)

        # ── 5. Input guardrails ───────────────────────────────────────────
        guard = self._guardrails.check_input(request.message)
        if not guard.passed:
            return await self._blocked_response(
                session=session,
                request=request,
                reason=guard.reason or "",
                safe_response=guard.safe_response or "",
                t_start=t_start,
            )

        # ── 6. Intent classification ──────────────────────────────────────
        intent = self._guardrails.classify_intent(request.message)

        # ── 7. Extract slots + people from message ───────────────────────
        slots = self._extract_slots(request.message, slots)

        # Extract people mentions — stored in profile for cross-session memory
        # "my friend who runs" in session 1 → remembered in session 2
        people = self._memory.extract_people_from_message(request.message)

        # ── 7b. Commerce intent routing (feature-flag gated) ─────────────
        commerce_intent = _classify_commerce_intent(request.message)
        if commerce_intent:
            commerce_response = await self._handle_commerce_intent(
                commerce_intent=commerce_intent,
                message=request.message,
                session=session,
                request=request,
                slots=slots,
                t_start=t_start,
            )
            if commerce_response is not None:
                return commerce_response
            # If None, fall through to normal LLM flow (e.g. flag disabled)

        # ── 8. Resolve active skills ─────────────────────────────────────
        skill_ctx = SkillContext(
            message=request.message,
            intent=intent,
            slots=slots,
            customer_profile=customer_profile,
            session_context=session.context or {},
            turn_count=session.message_count,
        )
        skill_result = self._skills.resolve(skill_ctx)

        # ── 9. LLM tool decision (skill prompts injected) ─────────────────
        if skill_result.prompt_addon:
            tool_system_prompt = TOOL_SELECTION_PROMPT + "\n\n" + skill_result.prompt_addon
        else:
            tool_system_prompt = TOOL_SELECTION_PROMPT
        active_tools = TOOL_DEFINITIONS + skill_result.extra_tools

        # Token-budget-aware history trimming:
        # Walk backwards through turns, accumulating estimated tokens until
        # the budget is exhausted.  Always keep the last 2 turns (1 exchange)
        # and never exceed 6 turns (same cap as before).
        _max_turns = 6
        _min_turns = 2
        _budget = HISTORY_TOKEN_BUDGET
        _candidates = conversation.recent_turns[-_max_turns:]
        llm_history: list[dict] = []
        _token_sum = 0
        for turn in reversed(_candidates):
            est_tokens = len(turn["content"]) // 4
            if llm_history and len(llm_history) >= _min_turns and _token_sum + est_tokens > _budget:
                break
            llm_history.append({"role": turn["role"], "content": turn["content"]})
            _token_sum += est_tokens
        llm_history.reverse()  # restore chronological order
        try:
            tool_call: ToolCall = await self._llm.decide_tool(
                system_prompt=tool_system_prompt,
                user_message=request.message,
                history=llm_history,
                tools=active_tools,
            )
        except LLMError:
            return await self._error_response(session, request, t_start)

        tool_name = tool_call.tool_name
        tool_args = self._enrich_tool_args(tool_name, tool_call.tool_args, slots, request.filters)

        logger.info("chat.tool_selected", session_id=str(session.session_id), tool=tool_name, intent=intent)

        # ── 9. No-cost shortcut responses ─────────────────────────────────
        if tool_name == "clarify_question":
            question = tool_args.get("question", "Could you tell me a bit more?")
            return await self._question_response(session, request, question, intent, t_start)

        if tool_name == "direct_answer":
            answer = tool_args.get("content", "")
            return await self._direct_response(session, request, answer, intent, t_start)

        # ── 10. Execute tool ──────────────────────────────────────────────
        tool_result = await self._tools.execute(tool_name, tool_args)

        # ── 11. Build prompt ──────────────────────────────────────────────
        system_prompt, _, citation_map = self._prompt.build(
            user_message=request.message,
            history=conversation,
            retrieved_chunks=tool_result.retrieved_chunks,
            slots=slots,
            customer_profile=customer_profile,
            shown_products=shown_products,
            tool_context=tool_result.summary,
        )

        # ── 12. Generate response ──────────────────────────────────────────
        try:
            llm_result = await self._llm.generate(
                system_prompt=system_prompt,
                user_message=request.message,
                history=llm_history,
                tool_result_summary=tool_result.summary,
                tool_name=tool_name,
            )
        except LLMError:
            return await self._error_response(session, request, t_start)

        # ── 13. Output guardrails ──────────────────────────────────────────
        out_guard = self._guardrails.check_output(
            llm_result.content,
            [c.product_id for c in tool_result.retrieved_chunks],
        )
        final_text = llm_result.content
        guard_status = GuardrailStatus.PASSED
        if not out_guard.passed:
            final_text   = out_guard.safe_response or final_text
            guard_status = GuardrailStatus.WARNED

        # ── 14. Citation processing ────────────────────────────────────────
        answer, answer_html, cited_products = self._citations.process(
            final_text, citation_map
        )

        # ── 15. Persist everything ────────────────────────────────────────
        await self._message_repo.create(
            session_id=session.session_id,
            role=MessageRole.USER,
            content=request.message,
            intent=intent,
            guardrail_status=GuardrailStatus.PASSED,
        )
        bot_msg = await self._message_repo.create(
            session_id=session.session_id,
            role=MessageRole.ASSISTANT,
            content=answer,
            intent=intent,
            guardrail_status=guard_status,
            cited_products=[p.model_dump() for p in cited_products],
            input_tokens=llm_result.input_tokens,
            output_tokens=llm_result.output_tokens,
            latency_ms=int((time.monotonic() - t_start) * 1000),
            llm_model=llm_result.model,
        )
        await self._session_repo.increment_counters(
            session_id=session.session_id,
            turn_delta=2,
            token_delta=llm_result.input_tokens + llm_result.output_tokens,
        )
        await self._memory.persist_session_memory(
            session=session,
            slots=slots,
            cited_products=cited_products,
            intent=intent,
        )
        await self._db.commit()

        # ── 16. Background tasks ──────────────────────────────────────────
        self._schedule_background_tasks(
            session_id=session.session_id,
            customer_id=session.customer_id,
            slots=slots,
            cited_products=cited_products,
            intent=intent,
            people=people,
        )

        # ── 17. Suggestions (LLM-generated, rule-based fallback) ────────
        suggestions_list = self._build_suggestions(llm_result.suggestions)

        latency_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "chat.complete",
            session_id=str(session.session_id),
            tool=tool_name,
            latency_ms=latency_ms,
            citations=len(cited_products),
            suggestions=len(suggestions_list),
            skills=skill_result.metadata.get("active_skills", []),
            tokens=llm_result.input_tokens + llm_result.output_tokens,
        )

        return ChatResponse(
            message_id=bot_msg.message_id,
            session_id=session.session_id,
            answer=answer,
            answer_html=answer_html,
            cited_products=cited_products,
            suggestions=suggestions_list,
            intent=intent,
            guardrail_status=guard_status,
            blocked=False,
            latency_ms=latency_ms,
            tokens_used=llm_result.input_tokens + llm_result.output_tokens,
        )

    async def handle_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """
        Streaming version of handle().
        Yields SSE-formatted events:
          data: {"type":"token","content":"..."}
          data: {"type":"done","message_id":"...","answer_html":"...","cited_products":[...],"suggestions":[...]}
          data: {"type":"error","content":"..."}
        """
        t_start = time.monotonic()

        def _sse(data: dict) -> str:
            return f"data: {json.dumps(data)}\n\n"

        async def _stream_words(text: str):
            """Yield text word-by-word with small delays for typewriter effect."""
            words = text.split(" ")
            for i, word in enumerate(words):
                token = word if i == 0 else " " + word
                yield _sse({"type": "token", "content": token})
                await asyncio.sleep(0.02)

        # ── Steps 1-8: same as non-streaming handle ──────────────────────
        try:
            await self._rate_limiter.check(request.customer_id)
            session = await self._resolve_session(request)
            await self._check_session_health(session)

            customer_profile, conversation = await asyncio.gather(
                self._memory.load_customer_profile(session.customer_id),
                self._load_history(session),
            )
            slots = self._memory.load_slots(session)
            shown_products = self._memory.load_shown_products(session)

            if session.message_count == 0 and customer_profile:
                slots = self._memory.prefill_slots_from_profile(slots, customer_profile)

            guard = self._guardrails.check_input(request.message)
            if not guard.passed:
                safe = guard.safe_response or "I can only help with shopping-related questions."
                async for event in _stream_words(safe):
                    yield event
                yield _sse({"type": "done", "message_id": "", "answer_html": safe,
                            "cited_products": [], "suggestions": []})
                return

            intent = self._guardrails.classify_intent(request.message)
            slots = self._extract_slots(request.message, slots)
            people = self._memory.extract_people_from_message(request.message)

            skill_ctx = SkillContext(
                message=request.message, intent=intent, slots=slots,
                customer_profile=customer_profile,
                session_context=session.context or {},
                turn_count=session.message_count,
            )
            skill_result = self._skills.resolve(skill_ctx)

            if skill_result.prompt_addon:
                tool_system_prompt = TOOL_SELECTION_PROMPT + "\n\n" + skill_result.prompt_addon
            else:
                tool_system_prompt = TOOL_SELECTION_PROMPT
            active_tools = TOOL_DEFINITIONS + skill_result.extra_tools

            candidates = conversation.recent_turns[-6:]
            budget = HISTORY_TOKEN_BUDGET
            selected: list[dict] = []
            for turn in reversed(candidates):
                cost = len(turn["content"]) // 4
                if budget - cost < 0 and len(selected) >= 2:
                    break
                selected.append(turn)
                budget -= cost
            llm_history = [{"role": t["role"], "content": t["content"]} for t in reversed(selected)]

            tool_call: ToolCall = await self._llm.decide_tool(
                system_prompt=tool_system_prompt,
                user_message=request.message,
                history=llm_history,
                tools=active_tools,
            )
        except LLMError:
            msg = "I'm having trouble right now. Please try again."
            async for event in _stream_words(msg):
                yield event
            yield _sse({"type": "done", "message_id": "", "answer_html": "",
                        "cited_products": [], "suggestions": []})
            return
        except Exception as exc:
            logger.error("stream.setup_failed", error=str(exc))
            yield _sse({"type": "error", "content": "Something went wrong. Please try again."})
            return

        tool_name = tool_call.tool_name
        tool_args = self._enrich_tool_args(tool_name, tool_call.tool_args, slots, request.filters)

        # ── Shortcut responses (stream word-by-word for typewriter effect) ─
        if tool_name == "clarify_question":
            q = tool_args.get("question", "Could you tell me a bit more?")
            async for event in _stream_words(q):
                yield event
            await self._persist_shortcut(session, request, q, intent, t_start)
            yield _sse({"type": "done", "message_id": "", "answer_html": q,
                        "cited_products": [], "suggestions": self._rule_based_suggestions(intent, tool_name, slots)})
            return

        if tool_name == "direct_answer":
            a = tool_args.get("content", "")
            async for event in _stream_words(a):
                yield event
            await self._persist_shortcut(session, request, a, intent, t_start)
            yield _sse({"type": "done", "message_id": "", "answer_html": a,
                        "cited_products": [], "suggestions": self._rule_based_suggestions(intent, tool_name, slots)})
            return

        # ── Execute tool + build prompt ──────────────────────────────────
        try:
            tool_result = await self._tools.execute(tool_name, tool_args)
            system_prompt, _, citation_map = self._prompt.build(
                user_message=request.message,
                history=conversation,
                retrieved_chunks=tool_result.retrieved_chunks,
                slots=slots,
                customer_profile=customer_profile,
                shown_products=shown_products,
                tool_context=tool_result.summary,
            )
        except Exception as exc:
            logger.error("stream.tool_failed", error=str(exc))
            msg = "I couldn't find what you're looking for. Please try rephrasing."
            async for event in _stream_words(msg):
                yield event
            yield _sse({"type": "done", "message_id": "", "answer_html": "",
                        "cited_products": [], "suggestions": []})
            return

        # ── Stream LLM tokens ────────────────────────────────────────────
        full_text = ""
        try:
            async for token in self._llm.generate_stream(
                system_prompt=system_prompt,
                user_message=request.message,
                history=llm_history,
                tool_result_summary=tool_result.summary,
                tool_name=tool_name,
            ):
                full_text += token
                yield _sse({"type": "token", "content": token})
        except LLMError:
            if not full_text:
                full_text = "I'm having trouble right now. Please try again."
                yield _sse({"type": "token", "content": full_text})

        # ── Post-stream: guardrails, citations, persist ──────────────────
        out_guard = self._guardrails.check_output(
            full_text, [c.product_id for c in tool_result.retrieved_chunks]
        )
        final_text = full_text
        guard_status = GuardrailStatus.PASSED
        if not out_guard.passed:
            final_text = out_guard.safe_response or final_text
            guard_status = GuardrailStatus.WARNED

        answer, answer_html, cited_products = self._citations.process(final_text, citation_map)

        await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.USER,
            content=request.message, intent=intent,
            guardrail_status=GuardrailStatus.PASSED,
        )
        bot_msg = await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.ASSISTANT,
            content=answer, intent=intent, guardrail_status=guard_status,
            cited_products=[p.model_dump() for p in cited_products],
            latency_ms=int((time.monotonic() - t_start) * 1000),
        )
        est_tokens = len(full_text) // 4
        await self._session_repo.increment_counters(
            session.session_id, turn_delta=2, token_delta=est_tokens,
        )
        await self._memory.persist_session_memory(
            session=session, slots=slots, cited_products=cited_products, intent=intent,
        )
        await self._db.commit()

        self._schedule_background_tasks(
            session_id=session.session_id, customer_id=session.customer_id,
            slots=slots, cited_products=cited_products, intent=intent, people=people,
        )

        # LLM suggestions from the same JSON response (zero extra calls)
        llm_suggestions = self._llm.parse_stream_suggestions()
        if llm_suggestions:
            suggestions = self._build_suggestions(llm_suggestions)
        else:
            # Fallback to rule-based if LLM JSON didn't parse
            suggestions = self._rule_based_suggestions(intent, tool_name, slots, cited_products)

        yield _sse({
            "type": "done",
            "message_id": str(bot_msg.message_id),
            "session_id": str(session.session_id),
            "answer_html": answer_html,
            "cited_products": [p.model_dump() for p in cited_products],
            "suggestions": suggestions,
            "intent": intent,
        })

    async def _persist_shortcut(self, session, request, content, intent, t_start):
        """Persist messages for shortcut (non-streamed) responses."""
        await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.USER,
            content=request.message, intent=intent,
            guardrail_status=GuardrailStatus.PASSED,
        )
        await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.ASSISTANT,
            content=content, guardrail_status=GuardrailStatus.PASSED,
            latency_ms=int((time.monotonic() - t_start) * 1000),
        )
        await self._session_repo.increment_counters(session.session_id, turn_delta=2)
        await self._db.commit()

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_suggestions(
        llm_suggestions: list[SuggestionItem] | None,
    ) -> list[dict]:
        """Convert LLM-generated suggestions to dicts for the response."""
        if not llm_suggestions:
            return []
        return [
            {"label": s.label, "message": s.message, "chip_type": "quick_reply"}
            for s in llm_suggestions
        ]

    @staticmethod
    def _rule_based_suggestions(
        intent: str, tool_name: str, slots: SlotState,
        cited_products: list[ProductCardDTO] | None = None,
    ) -> list[dict]:
        """
        Context-aware suggestions — zero LLM calls.
        Uses intent, tool, slots, and cited products for relevance.
        """
        s = lambda label, msg: {"label": label, "message": msg, "chip_type": "quick_reply"}
        products = cited_products or []

        def _short_name(name: str, max_len: int = 25) -> str:
            """Truncate product name for chip label."""
            clean = name.split("|")[0].split("for")[0].strip()
            return clean[:max_len] + "..." if len(clean) > max_len else clean

        # ── Search results shown ─────────────────────────────────────
        if tool_name == "search_products" and products:
            items: list[dict] = []
            # Suggest comparing top 2 products if we have 2+
            if len(products) >= 2:
                n1 = _short_name(products[0].productName)
                n2 = _short_name(products[1].productName)
                items.append(s(
                    f"Compare {n1} vs {n2}"[:35],
                    f"Compare {products[0].productName} and {products[1].productName}",
                ))
            # Suggest details on first product
            if products:
                items.append(s(
                    f"More on {_short_name(products[0].productName)}"[:35],
                    f"Tell me more about {products[0].productName}",
                ))
            # Budget-aware suggestions
            if slots.budget and products:
                cheaper = [p for p in products if p.price and p.price < slots.budget * 0.7]
                if cheaper:
                    items.append(s("Show cheaper options", f"Show me shoes under ₹{int(slots.budget * 0.5)}"))
                else:
                    items.append(s("Higher budget", f"Show me shoes up to ₹{int(slots.budget * 1.5)}"))
            elif not slots.budget:
                items.append(s("Under ₹2000", "Show me shoes under 2000"))
            # Missing slot suggestions
            if not slots.size:
                items.append(s("Check my size", "Do you have these in my size?"))
            elif not slots.brand:
                items.append(s("Other brands", "Show me shoes from other brands"))
            return items[:4]

        # ── Search with no results ───────────────────────────────────
        if tool_name == "search_products" and not products:
            items = []
            if slots.brand:
                items.append(s("Try other brands", "Show me shoes from any brand"))
            if slots.budget:
                items.append(s("Higher budget", f"Show me shoes up to ₹{int(slots.budget * 2)}"))
            items.append(s("Popular shoes", "Show me your most popular shoes"))
            items.append(s("Running shoes", "Show me running shoes"))
            return items[:4]

        # ── Comparison ───────────────────────────────────────────────
        if tool_name == "compare_products":
            items = []
            for p in products[:2]:
                name = _short_name(p.productName)
                items.append(s(f"More on {name}"[:35], f"Tell me more about {p.productName}"))
            if not slots.size:
                items.append(s("Check size availability", "Do you have these in my size?"))
            items.append(s("Show similar shoes", "Show me similar shoes to these"))
            return items[:4]

        # ── Greeting ─────────────────────────────────────────────────
        if intent == "greeting":
            return [
                s("Running shoes", "I need running shoes"),
                s("Casual shoes", "Show me casual shoes"),
                s("What's popular?", "What are your most popular shoes?"),
            ]

        # ── Size/stock queries ───────────────────────────────────────
        if tool_name in ("size_advice", "stock_check"):
            items = []
            if products:
                items.append(s(
                    f"Buy {_short_name(products[0].productName)}"[:35],
                    f"Tell me more about {products[0].productName}",
                ))
            items.append(s("Different size", "Show me shoes in a different size"))
            items.append(s("Similar shoes", "Show me similar shoes"))
            return items[:4]

        # ── Gift finding ─────────────────────────────────────────────
        if tool_name == "gift_finder":
            items = []
            if products:
                items.append(s(
                    f"More on {_short_name(products[0].productName)}"[:35],
                    f"Tell me more about {products[0].productName}",
                ))
            items.append(s("Different budget", "Show me gifts in a different price range"))
            items.append(s("Other gift ideas", "What else would make a good gift?"))
            return items[:4]

        # ── Policy/FAQ ───────────────────────────────────────────────
        if tool_name in ("policy_faq", "return_request"):
            return [
                s("Browse shoes", "Show me shoes"),
                s("Return process", "How do I return a product?"),
                s("Shipping info", "What are your shipping options?"),
            ]

        # ── Default ──────────────────────────────────────────────────
        return [
            s("Browse shoes", "Show me popular shoes"),
            s("Help me choose", "I need help choosing the right shoes"),
        ]

    async def _resolve_session(self, request: ChatRequest) -> Session:
        """
        Auto-session resolution:
          If session_id provided → use that session
          If only customer_id   → find active session or create new
          If neither            → create anonymous session
        """
        if request.session_id:
            session = await self._session_repo.get_by_id(request.session_id)
            if not session:
                raise SessionNotFoundError(f"Session {request.session_id} not found.")
            return session

        session, created = await self._session_repo.get_or_create(
            customer_id=request.customer_id,
            channel=request.channel,
        )
        if created:
            logger.info(
                "chat.session_auto_created",
                session_id=str(session.session_id),
                customer_id=str(request.customer_id) if request.customer_id else "guest",
            )
        return session

    async def _check_session_health(self, session: Session) -> None:
        if session.status == SessionStatus.EXPIRED:
            raise SessionExpiredError()
        if session.status != SessionStatus.ACTIVE:
            raise SessionInactiveError(f"Session is {session.status}.")
        if session.total_tokens >= settings.SESSION_TOKEN_BUDGET:
            raise TokenBudgetExceededError()

    async def _load_history(self, session: Session) -> ConversationHistory:
        messages = await self._message_repo.get_recent_turns(
            session_id=session.session_id,
            limit=settings.CONVERSATION_WINDOW_TURNS * 2,
        )
        return ConversationHistory(
            recent_turns=[
                {"role": m.role.value.lower() if isinstance(m.role, MessageRole) else m.role.lower(), "content": m.content}
                for m in messages
            ],
            summary=self._memory.load_summary(session),
        )

    def _extract_slots(self, message: str, existing: SlotState) -> SlotState:
        """
        Extract structured slot data from the message.
        All keyword lists and thresholds come from config/business_rules.json.
        Enriches the LLM's search query — doesn't gate the conversation.
        """
        msg = message.lower()
        br  = business_rules()
        slot_cfg   = br["slot_extraction"]
        budget_cfg = br["budget"]

        # Reset signal
        reset_phrases = "|".join(re.escape(p) for p in slot_cfg["reset_phrases"])
        if re.search(rf'\b({reset_phrases})\b', msg, re.I):
            return SlotState()

        slots = SlotState(
            category=existing.category,
            use_case=existing.use_case,
            brand=existing.brand,
            budget=existing.budget,
            size=existing.size,
            color=existing.color,
        )

        # Category — from JSON
        for cat, keywords in slot_cfg["categories"].items():
            if any(kw in msg for kw in keywords):
                slots.category = cat
                break

        # Use case — from JSON
        for use, keywords in slot_cfg["use_cases"].items():
            if any(re.search(r'\b' + k + r'\b', msg) for k in keywords):
                slots.use_case = use
                break

        # Brand — from JSON
        for brand in slot_cfg["brands"]:
            if brand in msg:
                slots.brand = brand.title()
                break
        no_brand_pattern = "|".join(re.escape(p) for p in slot_cfg["no_brand_phrases"])
        if re.search(rf'\b({no_brand_pattern})\b', msg, re.I):
            slots.brand = "any"

        # Budget — explicit number first, then keyword fallback
        budget_match = re.search(
            r'(?:under|below|less than|up to|max|around|about)\s*\$?\s*(\d+)', msg, re.I
        )
        if budget_match:
            slots.budget = float(budget_match.group(1))
        elif any(kw in msg for kw in slot_cfg["budget_keywords"]["cheap"]):
            slots.budget = float(budget_cfg["cheap_keyword_default"])
        elif any(kw in msg for kw in slot_cfg["budget_keywords"]["no_limit"]):
            slots.budget = float(budget_cfg["unlimited_sentinel"])

        # Size
        size_match = re.search(
            r'\b(?:size\s*)?([4-9]|1[0-5])(?:\.5)?\b|\b(xs|s|m|l|xl|xxl)\b', msg, re.I
        )
        if size_match:
            raw = (size_match.group(1) or size_match.group(2) or "").strip()
            size_map = {"xs": "XS", "s": "S", "m": "M", "l": "L", "xl": "XL", "xxl": "XXL"}
            slots.size = size_map.get(raw.lower(), raw)

        # Color — from JSON
        colors = slot_cfg["colors"]
        color_pattern = "|".join(colors)
        color_match = re.search(rf'\b({color_pattern})\b', msg, re.I)
        if color_match:
            slots.color = color_match.group(0).lower()

        return slots

    def _enrich_tool_args(
        self,
        tool_name: str,
        args: dict,
        slots: SlotState,
        extra_filters: dict,
    ) -> dict:
        """
        Inject collected slots into tool args before execution.
        Makes RAG searches precise — brand, price, size as real filters.
        Does NOT override what the LLM already extracted.
        """
        if tool_name not in ("search_products", "outfit_pairing", "gift_finder"):
            return args

        unlimited = business_rules()["budget"]["unlimited_sentinel"]

        enriched = dict(args)
        if slots.brand and slots.brand.lower() not in ("any", "no preference"):
            enriched.setdefault("brand", slots.brand)
        if slots.budget and slots.budget < unlimited:
            enriched.setdefault("max_price", slots.budget)
        if slots.size:
            enriched.setdefault("size", slots.size)
        if slots.use_case:
            enriched.setdefault("use_case", slots.use_case)
        if slots.category:
            enriched.setdefault("category", slots.category)

        # Build richer query if current query is vague (1-2 words)
        current_query = enriched.get("query", "")
        if len(current_query.split()) <= 2 and slots.category:
            enriched["query"] = slots.to_search_query()

        if extra_filters:
            enriched["_extra_filters"] = extra_filters

        return enriched

    def _schedule_background_tasks(
        self,
        session_id: uuid.UUID,
        customer_id: uuid.UUID | None,
        slots: SlotState,
        cited_products: list[ProductCardDTO],
        intent: str,
        people: list[PersonNote] | None = None,
    ) -> None:
        """Schedule background work. Each task creates its own DB session."""
        if customer_id:
            asyncio.create_task(
                _bg_update_profile(customer_id, slots, cited_products, intent, people or [])
            )
        asyncio.create_task(_bg_summarise(session_id))

    # ── Instant response builders ─────────────────────────────────────────

    async def _handle_commerce_intent(
        self,
        commerce_intent: str,
        message: str,
        session: Session,
        request: ChatRequest,
        slots: SlotState,
        t_start: float,
    ) -> ChatResponse | None:
        """
        Route a commerce intent through feature flags → slot validation → CommerceClient.

        Returns:
          - ChatResponse if the intent was handled (flag disabled, slot missing, or service called)
          - None if the intent should fall through to the normal LLM flow
        """
        customer_id_str = str(session.customer_id) if session.customer_id else None

        # ── Feature flag check ────────────────────────────────────────────
        if not self._flags.is_intent_enabled(commerce_intent, customer_id_str):
            logger.info(
                "chat.commerce_intent_disabled",
                intent=commerce_intent,
                session_id=str(session.session_id),
            )
            msg = (
                "This feature is currently unavailable. "
                "Our team is working on it — please check back soon!"
            )
            return await self._direct_response(session, request, msg, commerce_intent, t_start)

        # ── Resolve ambiguous product references via RAG ──────────────────
        commerce_slots = await self._extract_commerce_slots(
            message=message,
            intent=commerce_intent,
            session=session,
        )

        # ── Slot validation — re-prompt for missing required slots ────────
        required = _REQUIRED_SLOTS.get(commerce_intent, [])
        for slot_name in required:
            if not commerce_slots.get(slot_name):
                prompt_question = _SLOT_PROMPTS.get(
                    slot_name,
                    f"Could you provide the {slot_name.replace('_', ' ')}?",
                )
                logger.info(
                    "chat.commerce_slot_missing",
                    intent=commerce_intent,
                    missing_slot=slot_name,
                )
                return await self._question_response(
                    session, request, prompt_question, commerce_intent, t_start
                )

        # ── Call commerce service ─────────────────────────────────────────
        try:
            service_response = await self._dispatch_commerce_intent(
                intent=commerce_intent,
                slots=commerce_slots,
                customer_id=customer_id_str or "",
                request_id=str(session.session_id),
            )
        except Exception as exc:
            logger.warning(
                "chat.commerce_dispatch_failed",
                intent=commerce_intent,
                error=str(exc),
            )
            return await self._error_response(session, request, t_start)

        # ── Format response ───────────────────────────────────────────────
        answer = self._format_commerce_response(commerce_intent, service_response)
        return await self._direct_response(session, request, answer, commerce_intent, t_start)

    async def _extract_commerce_slots(
        self,
        message: str,
        intent: str,
        session: Session,
    ) -> dict:
        """
        Extract commerce-specific slots from the message.
        Resolves ambiguous product references ("the blue one") via RAG.
        """
        import re
        slots: dict = {}
        msg = message.lower()

        # Extract order_id — matches patterns like #12345, order 12345, ORD-12345
        order_id_match = re.search(
            r'(?:order\s*#?\s*|#\s*)([A-Za-z0-9_-]{4,})', message, re.IGNORECASE
        )
        if order_id_match:
            slots["order_id"] = order_id_match.group(1)

        # Extract quantity — "2 pairs", "3 items", "one", etc.
        qty_match = re.search(
            r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b', msg
        )
        if qty_match:
            word_to_num = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            }
            raw = qty_match.group(1)
            slots["quantity"] = word_to_num.get(raw, int(raw) if raw.isdigit() else 1)

        # Resolve product reference via RAG if needed
        if intent in ("add_to_cart", "remove_from_cart") and "product_id" not in slots:
            # Check for ambiguous references ("the blue one", "that item", "it")
            ambiguous_patterns = [
                r'\bthe\s+\w+\s+one\b',
                r'\bthat\s+(item|product|one|thing)\b',
                r'\bthis\s+(item|product|one|thing)\b',
                r'\bit\b',
            ]
            is_ambiguous = any(re.search(p, msg) for p in ambiguous_patterns)

            # Try to extract explicit product name/id first
            product_match = re.search(
                r'(?:product\s+(?:id\s+)?|item\s+(?:id\s+)?)([A-Za-z0-9_-]+)', message, re.IGNORECASE
            )
            if product_match:
                slots["product_id"] = product_match.group(1)
            elif is_ambiguous or intent == "add_to_cart":
                # Resolve via RAG — use the message as the search query
                chunks = await self._rag.retrieve(
                    query=message,
                    filters={"doc_type": "product"},
                    top_k=1,
                    request_id=None,
                )
                if chunks:
                    slots["product_id"] = chunks[0].product_id
                    slots["_resolved_product_name"] = chunks[0].content[:80]

        # For checkout_initiate, line_items come from the session context (cart)
        if intent == "checkout_initiate":
            cart = session.context.get("cart", {})
            line_items = cart.get("line_items", [])
            if line_items:
                slots["line_items"] = line_items

        # Extract buyer info (name, email)
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', message)
        if email_match:
            slots["buyer_email"] = email_match.group(0)

        return slots

    async def _dispatch_commerce_intent(
        self,
        intent: str,
        slots: dict,
        customer_id: str,
        request_id: str,
    ):
        """Route a validated commerce intent to the CommerceClient."""
        from app.clients.commerce_client import CommerceResponse

        if intent == "add_to_cart":
            line_item = {
                "item": {"id": slots["product_id"], "title": slots.get("_resolved_product_name", slots["product_id"])},
                "quantity": slots.get("quantity", 1),
            }
            return await self._commerce.create_checkout_session(
                customer_id=customer_id,
                line_items=[line_item],
                request_id=request_id,
            )

        elif intent == "remove_from_cart":
            # Update session with item removed — get current session first
            current = await self._commerce.get_checkout_session(
                session_id=slots.get("checkout_session_id", ""),
                request_id=request_id,
            )
            existing_items = current.data.get("line_items_snapshot", [])
            updated_items = [
                item for item in existing_items
                if item.get("item", {}).get("id") != slots["product_id"]
            ]
            if current.success and current.data.get("session_id"):
                return await self._commerce.update_checkout_session(
                    session_id=current.data["session_id"],
                    line_items=updated_items,
                    request_id=request_id,
                )
            # No active session — nothing to remove
            from app.clients.commerce_client import CommerceResponse
            return CommerceResponse(success=True, data={"message": "Cart is already empty."})

        elif intent == "view_cart":
            # Return current cart state — use a placeholder session lookup
            from app.clients.commerce_client import CommerceResponse
            return CommerceResponse(
                success=True,
                data={"message": "view_cart", "customer_id": customer_id},
            )

        elif intent == "checkout_initiate":
            return await self._commerce.create_checkout_session(
                customer_id=customer_id,
                line_items=slots.get("line_items", []),
                buyer={"email": slots["buyer_email"]} if slots.get("buyer_email") else None,
                request_id=request_id,
            )

        elif intent == "order_status":
            return await self._commerce.get_order(
                order_id=slots["order_id"],
                customer_id=customer_id,
                request_id=request_id,
            )

        elif intent == "order_history":
            return await self._commerce.list_orders(
                customer_id=customer_id,
                request_id=request_id,
            )

        elif intent == "cancel_order":
            return await self._commerce.cancel_order(
                order_id=slots["order_id"],
                customer_id=customer_id,
                request_id=request_id,
            )

        else:
            from app.clients.commerce_client import CommerceResponse
            return CommerceResponse(
                success=False,
                data={},
                error_code="unknown_intent",
                error_message=f"Unknown commerce intent: {intent}",
            )

    def _format_commerce_response(self, intent: str, response) -> str:
        """
        Format a CommerceResponse into a natural language reply.
        When requires_escalation, format continue_url as a clickable markdown link.
        """
        # Handle requires_escalation — surface continue_url as a clickable link
        if response.requires_escalation and response.continue_url:
            return (
                "To complete your checkout, please visit the merchant's secure checkout page: "
                f"[Complete your checkout here]({response.continue_url})"
            )

        if not response.success:
            error_messages = {
                "out_of_stock":            "Sorry, that item is currently out of stock.",
                "cart_limit_exceeded":     "Your cart is full (50 items maximum).",
                "payment_failed":          "The payment could not be processed. Please try a different payment method.",
                "session_not_found":       "I couldn't find an active checkout session. Would you like to start a new one?",
                "checkout_expired":        "Your checkout session has expired. Would you like to start over?",
                "not_found":               "I couldn't find that order. Please check the order number and try again.",
                "cancellation_not_allowed": "This order can't be cancelled because it has already shipped.",
                "return_not_eligible":     "This order isn't eligible for a return yet.",
                "commerce_unavailable":    "The commerce service is temporarily unavailable. Please try again in a moment.",
            }
            return error_messages.get(
                response.error_code or "",
                "Something went wrong. Please try again.",
            )

        data = response.data

        if intent == "add_to_cart":
            items = data.get("line_items_snapshot", [])
            count = len(items)
            return f"Added to your cart! You now have {count} item{'s' if count != 1 else ''} in your cart."

        elif intent == "remove_from_cart":
            return "Removed from your cart."

        elif intent == "view_cart":
            items = data.get("line_items_snapshot", [])
            if not items:
                return "Your cart is empty. Would you like to browse some products?"
            lines = []
            for item in items:
                product = item.get("item", {})
                qty = item.get("quantity", 1)
                title = product.get("title", "Item")
                price_cents = product.get("price", 0)
                price = price_cents / 100 if price_cents else 0
                lines.append(f"- {title} × {qty} (${price:.2f} each)")
            totals = data.get("totals_snapshot", {})
            subtotal = totals.get("subtotal_cents", 0) / 100
            summary = "\n".join(lines)
            return f"Here's what's in your cart:\n{summary}\n\nSubtotal: ${subtotal:.2f}"

        elif intent == "checkout_initiate":
            status = data.get("ucp_status", data.get("status", ""))
            session_id = data.get("session_id", "")
            if status == "incomplete":
                return (
                    "I've started your checkout. "
                    "Please provide your shipping address to continue."
                )
            return f"Checkout session created (status: {status})."

        elif intent == "order_status":
            status = data.get("status", "unknown")
            order_id = data.get("ucp_order_id", data.get("order_id", ""))
            fulfillment = data.get("fulfillment", {})
            tracking = None
            for event in fulfillment.get("events", []):
                if event.get("type") == "shipped":
                    tracking = event.get("tracking_number")
                    break
            msg = f"Order {order_id} is currently **{status}**."
            if tracking:
                msg += f" Tracking number: {tracking}."
            return msg

        elif intent == "order_history":
            orders = data.get("orders", data.get("items", []))
            if not orders:
                return "You don't have any orders yet."
            lines = []
            for order in orders[:5]:
                oid = order.get("ucp_order_id", order.get("order_id", ""))
                status = order.get("status", "")
                totals = order.get("totals", {})
                total_cents = totals.get("grand_total_cents", 0)
                total = total_cents / 100 if total_cents else 0
                lines.append(f"- Order {oid}: {status} — ${total:.2f}")
            result = "Here are your recent orders:\n" + "\n".join(lines)
            if len(orders) > 5:
                result += f"\n\n...and {len(orders) - 5} more."
            return result

        elif intent == "cancel_order":
            order_id = data.get("ucp_order_id", data.get("order_id", ""))
            return f"Order {order_id} has been cancelled successfully."

        return "Done! Is there anything else I can help you with?"

    # ── Instant response builders ─────────────────────────────────────────

    async def _blocked_response(
        self, session, request, reason, safe_response, t_start
    ) -> ChatResponse:
        await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.USER, content=request.message,
            intent="blocked", guardrail_status=GuardrailStatus.BLOCKED, guardrail_reason=reason,
        )
        bot_msg = await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.ASSISTANT, content=safe_response,
            guardrail_status=GuardrailStatus.BLOCKED,
        )
        await self._session_repo.increment_counters(session.session_id, turn_delta=2)
        await self._db.commit()
        _, answer_html, _ = self._citations.process(safe_response, {})
        return ChatResponse(
            message_id=bot_msg.message_id, session_id=session.session_id,
            answer=safe_response, answer_html=answer_html, cited_products=[],
            intent="blocked", guardrail_status=GuardrailStatus.BLOCKED, blocked=True,
            latency_ms=int((time.monotonic() - t_start) * 1000), tokens_used=0,
        )

    async def _generate_suggestions_only(self, user_message: str, bot_response: str) -> list[dict]:
        """Quick LLM call to generate suggestions for shortcut responses."""
        try:
            result = await self._llm.generate(
                system_prompt=prompts()["inline"]["suggestions"],
                user_message=user_message,
                history=[],
                tool_result_summary=bot_response,
                tool_name="direct_answer",
            )
            return self._build_suggestions(result.suggestions)
        except Exception:
            return []

    async def _question_response(
        self, session, request, question, intent, t_start
    ) -> ChatResponse:
        await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.USER, content=request.message,
            intent=intent, guardrail_status=GuardrailStatus.PASSED,
        )
        bot_msg = await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.ASSISTANT, content=question,
            intent="slot_filling", guardrail_status=GuardrailStatus.PASSED, llm_model="rule_based",
        )
        await self._session_repo.increment_counters(session.session_id, turn_delta=2)
        await self._db.commit()
        _, answer_html, _ = self._citations.process(question, {})
        suggestions = await self._generate_suggestions_only(request.message, question)
        return ChatResponse(
            message_id=bot_msg.message_id, session_id=session.session_id,
            answer=question, answer_html=answer_html, cited_products=[],
            suggestions=suggestions,
            intent="slot_filling", guardrail_status=GuardrailStatus.PASSED, blocked=False,
            latency_ms=int((time.monotonic() - t_start) * 1000), tokens_used=0,
        )

    async def _direct_response(
        self, session, request, answer, intent, t_start
    ) -> ChatResponse:
        await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.USER, content=request.message,
            intent=intent, guardrail_status=GuardrailStatus.PASSED,
        )
        bot_msg = await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.ASSISTANT, content=answer,
            intent=intent, guardrail_status=GuardrailStatus.PASSED, llm_model="direct",
        )
        await self._session_repo.increment_counters(session.session_id, turn_delta=2)
        await self._db.commit()
        _, answer_html, _ = self._citations.process(answer, {})
        suggestions = await self._generate_suggestions_only(request.message, answer)
        return ChatResponse(
            message_id=bot_msg.message_id, session_id=session.session_id,
            answer=answer, answer_html=answer_html, cited_products=[],
            suggestions=suggestions,
            intent=intent, guardrail_status=GuardrailStatus.PASSED, blocked=False,
            latency_ms=int((time.monotonic() - t_start) * 1000), tokens_used=0,
        )

    async def _error_response(self, session, request, t_start) -> ChatResponse:
        msg = "I'm having a bit of trouble right now. Please try again in a moment."
        await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.USER, content=request.message, intent="error",
        )
        bot_msg = await self._message_repo.create(
            session_id=session.session_id, role=MessageRole.ASSISTANT, content=msg,
            guardrail_status=GuardrailStatus.PASSED, llm_model="fallback",
        )
        await self._session_repo.increment_counters(session.session_id, turn_delta=2)
        await self._db.commit()
        _, answer_html, _ = self._citations.process(msg, {})
        suggestions = await self._generate_suggestions_only(request.message, msg)
        return ChatResponse(
            message_id=bot_msg.message_id, session_id=session.session_id,
            answer=msg, answer_html=answer_html, cited_products=[],
            suggestions=suggestions,
            intent="error", guardrail_status=GuardrailStatus.PASSED, blocked=False,
            latency_ms=int((time.monotonic() - t_start) * 1000), tokens_used=0,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Background tasks — each uses its OWN DB session
# ─────────────────────────────────────────────────────────────────────────────

async def _bg_update_profile(
    customer_id: uuid.UUID,
    slots: SlotState,
    cited_products: list[ProductCardDTO],
    intent: str,
    people: list[PersonNote] | None = None,
) -> None:
    """Update customer profile in background. Never uses the request session."""
    from app.db.session import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            memory = MemoryService(
                session_repo=SessionRepository(db),
                customer_repo=CustomerRepository(db),
            )
            await memory.update_customer_profile(
                customer_id, slots, cited_products, intent, people or []
            )
            await db.commit()
    except Exception as exc:
        logger.warning("bg_profile.failed", customer_id=str(customer_id), error=str(exc))


async def _bg_summarise(session_id: uuid.UUID) -> None:
    """Summarise conversation in background. Never uses the request session."""
    from app.db.session import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            repo    = MessageRepository(db)
            sess_r  = SessionRepository(db)
            session = await sess_r.get_by_id(session_id)
            if not session:
                return
            if session.message_count < settings.CONVERSATION_MAX_TURNS_BEFORE_SUMMARY * 2:
                return

            messages = await repo.get_recent_turns(session_id, limit=100)
            if not messages:
                return

            transcript = "\n".join(
                f"{'Customer' if m.role == MessageRole.USER else 'Bot'}: {m.content}"
                for m in messages[:-12]   # summarise older turns, keep last 6
            )

            llm    = LLMClient()
            summary = await llm.summarise(transcript)

            memory = MemoryService(session_repo=sess_r, customer_repo=CustomerRepository(db))
            await memory.persist_summary(session_id, summary)
            await db.commit()
    except Exception as exc:
        logger.warning("bg_summarise.failed", session_id=str(session_id), error=str(exc))
