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
from app.services.checkout_tools import (
    CheckoutToolRegistry,
    CHECKOUT_TOOL_DEFINITIONS,
)
from app.services.stripe_customer_service import StripeCustomerService
from app.services.skills.skill_registry import SkillRegistry
from app.services.skills.base_skill import SkillContext
from app.services.skills.prompts import TOOL_SELECTION_PROMPT
from app.agent.skill_loader import skill_loader
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
    (["checkout", "check out", "place order", "place my order", "buy now",
      "proceed to checkout", "proceed to payment", "proceed with payment",
      "proceed with purchase", "place the order",
      "purchase this", "purchase it", "buy this", "buy it",
      "complete my purchase", "complete the purchase", "complete purchase",
      "confirm my purchase", "confirm purchase", "confirm the purchase",
      "confirm my order", "confirm order",
      "finalize", "finalise", "make the purchase",
      "pay for this", "payment for the", "i want to pay for",
      "i want to buy now", "i'd like to buy now", "buy it now", "purchase it now",
      "order it now", "buy sneakers now", "buy shoes now"], "checkout_initiate"),
    (["add to cart", "add to my cart", "put in cart", "put it in", "add it", "add this",
      "i want to add", "add the"], "add_to_cart"),
    (["remove from cart", "take out of cart", "delete from cart", "remove it", "take it out"], "remove_from_cart"),
    (["view cart", "show cart", "what's in my cart", "my cart", "see my cart", "show my cart"], "view_cart"),
    (["order status", "where is my order", "track my order", "order #", "order number",
      "status of my order", "where's my order"], "order_status"),
    (["order history", "my orders", "past orders", "previous orders", "all orders",
      "show my orders", "show orders", "see my orders"], "order_history"),
    (["cancel order", "cancel my order", "cancel purchase", "cancel the order"], "cancel_order"),
]

# Required slots per commerce intent
_REQUIRED_SLOTS: dict[str, list[str]] = {
    "add_to_cart":       ["product_id", "quantity"],
    "remove_from_cart":  ["product_id"],
    "view_cart":         [],
    "checkout_initiate": [],   # line_items built from cart or RAG-resolved product
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


# Phrases that signal purchase intent but need a specific product reference
# (e.g. "i want to buy the adidas shoe" → checkout, "i want to buy shoes" → search)
_PURCHASE_INTENT_PHRASES = [
    "i want to buy",
    "i'd like to buy",
    "i would like to buy",
    "i want to purchase",
    "i'd like to purchase",
    "i would like to purchase",
    "i want to order",
    "i'd like to order",
    "i would like to order",
]

# Generic category words that indicate browsing, not checkout
_BROWSE_CATEGORY_WORDS = {
    "shoes", "shoe", "sneakers", "boots", "sandals", "slippers",
    "shirts", "shirt", "pants", "jeans", "jacket", "jackets",
    "clothes", "clothing", "apparel", "dress", "dresses",
    "something", "anything", "some", "a few", "options",
}


def _is_specific_product_reference(msg: str, phrase: str) -> bool:
    """Check if text after the purchase phrase references a specific product (not a category)."""
    after = msg[msg.index(phrase) + len(phrase):].strip()
    # Strip trailing filler words like "now", "please", "today"
    for filler in (" now", " please", " today", " asap"):
        if after.endswith(filler):
            after = after[: -len(filler)].strip()
    if not after:
        return False
    # "i want to buy the adidas..." → specific product
    if after.startswith("the ") or after.startswith("this ") or after.startswith("that "):
        return True
    # Check first meaningful word — if it's a generic category, it's browsing
    first_word = after.split()[0].rstrip(".,!?") if after.split() else ""
    if first_word in _BROWSE_CATEGORY_WORDS:
        return False
    # If there are 2+ words after the phrase (after stripping fillers), likely a specific product name
    if len(after.split()) >= 2:
        return True
    return False


def _classify_commerce_intent(message: str) -> str | None:
    """
    Keyword-based commerce intent classifier.
    Returns a commerce intent name or None if no match.
    Zero LLM cost.
    """
    msg = message.lower()

    # First check the explicit keyword map
    for keywords, intent in _COMMERCE_INTENT_MAP:
        matched = [kw for kw in keywords if kw in msg]
        if matched:
            logger.info(
                "commerce_intent.classified",
                intent=intent,
                matched_keywords=matched,
                message_preview=msg[:80],
            )
            return intent

    # Then check ambiguous purchase phrases — only trigger if referencing a specific product
    for phrase in _PURCHASE_INTENT_PHRASES:
        if phrase in msg and _is_specific_product_reference(msg, phrase):
            logger.info(
                "commerce_intent.classified",
                intent="checkout_initiate",
                matched_keywords=[phrase],
                message_preview=msg[:80],
                reason="specific_product_reference",
            )
            return "checkout_initiate"

    logger.info(
        "commerce_intent.no_match",
        message_preview=msg[:80],
    )
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

        # Pre-fill slots for returning customers ONLY after they confirm "for myself"
        # Turn 0 = greeting, don't prefill yet (agent will ask "yourself or someone else?")
        # Turn 1+ = check if user indicated shopping for themselves
        if customer_profile and session.message_count > 0:
            msg_lower = request.message.lower()
            _self_signals = ["myself", "for me", "for myself", "me ", "i need", "i want", "i'm looking", "im looking", "my size"]
            _other_signals = ["someone", "someone else", "gift", "for my friend", "for my dad", "for my mom", "for my mum", "for my wife", "for my husband", "for my partner", "for him", "for her"]
            is_for_self = any(s in msg_lower for s in _self_signals)
            is_for_other = any(s in msg_lower for s in _other_signals)
            if is_for_self and not is_for_other:
                slots = self._memory.prefill_slots_from_profile(slots, customer_profile)
                # Never prefill budget — always ask fresh
                slots.budget = None

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

        # ── 7b. Checkout agent mode ─────────────────────────────────────
        if self._memory.get_active_agent(session) == "checkout":
            checkout_response = await self._handle_checkout_mode(
                session=session,
                request=request,
                customer_profile=customer_profile,
                conversation=conversation,
                t_start=t_start,
            )
            if checkout_response is not None:
                return checkout_response

        # ── 7c. Commerce intent routing (feature-flag gated) ─────────────
        commerce_intent = _classify_commerce_intent(request.message)

        # Enter checkout agent mode for checkout_initiate
        if commerce_intent == "checkout_initiate":
            # Create/get checkout session first
            commerce_slots = await self._extract_commerce_slots(
                message=request.message, intent=commerce_intent, session=session,
            )
            customer_id_str = str(session.customer_id) if session.customer_id else None
            try:
                service_response = await self._dispatch_commerce_intent(
                    intent=commerce_intent, slots=commerce_slots,
                    customer_id=customer_id_str or "",
                    request_id=str(session.session_id), session=session,
                )
                if service_response.success and service_response.data:
                    cs_id = (
                        service_response.data.get("sessionId")
                        or service_response.data.get("session_id", "")
                    )
                    if session.context is None:
                        session.context = {}
                    session.context["checkout_session_id"] = cs_id
            except Exception as exc:
                logger.warning("chat.checkout_session_create_failed", error=str(exc))

            await self._memory.set_active_agent(session, "checkout")
            # Rewrite message for the checkout agent — it should see a checkout
            # request, not the raw product query that triggered checkout_initiate
            checkout_request = ChatRequest(
                message="Customer wants to checkout. Present the order summary.",
                customer_id=request.customer_id,
                session_id=request.session_id,
                channel=request.channel,
            )
            return await self._handle_checkout_mode(
                session=session, request=checkout_request,
                customer_profile=customer_profile,
                conversation=conversation,
                t_start=t_start,
            )

        if commerce_intent:
            commerce_response = await self._handle_commerce_intent(
                commerce_intent=commerce_intent,
                message=request.message,
                session=session,
                request=request,
                slots=slots,
                customer_profile=customer_profile,
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

        # ── 9. LLM tool decision (skill prompts + slot status injected) ───
        slot_status = self._build_slot_status(slots)
        tool_system_prompt = TOOL_SELECTION_PROMPT + "\n\n" + slot_status
        if skill_result.prompt_addon:
            tool_system_prompt += "\n\n" + skill_result.prompt_addon
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
                image_base64=getattr(request, "image_base64", None),
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
                image_base64=getattr(request, "image_base64", None),
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

        # ── Generate title after 2nd user message ─────────────────────────
        if session.message_count == 4 and not session.title:
            logger.info(f"Triggering title generation for session {session.session_id}, message_count={session.message_count}")
            asyncio.create_task(self._generate_session_title(session.session_id))

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
            # SSE requires single-line data — ensure no newlines in JSON
            json_str = json.dumps(data, default=str, ensure_ascii=False)
            return f"data: {json_str}\n\n"

        async def _stream_words(text: str):
            """Yield text word-by-word with small delays for typewriter effect."""
            words = text.split(" ")
            for i, word in enumerate(words):
                token = word if i == 0 else " " + word
                yield _sse({"type": "token", "content": token})
                await asyncio.sleep(0.02)

        # ── Steps 1-8: same as non-streaming handle ──────────────────────
        # Send an initial heartbeat immediately so the client knows the connection is alive,
        # then continue sending heartbeats during the slow setup phase.
        yield ": heartbeat\n\n"
        try:
            setup_task = asyncio.ensure_future(self._run_stream_setup(request, t_start))
            while not setup_task.done():
                await asyncio.sleep(5)
                if not setup_task.done():
                    yield ": heartbeat\n\n"
            setup_result = await setup_task
        except Exception as exc:
            logger.error("stream.setup_failed", error=str(exc))
            yield _sse({"type": "error", "content": "Something went wrong. Please try again."})
            return

        # Unpack setup result
        if setup_result.get("early_return"):
            for event in setup_result["events"]:
                yield event
            return

        session        = setup_result["session"]
        conversation   = setup_result["conversation"]
        slots          = setup_result["slots"]
        shown_products = setup_result["shown_products"]
        customer_profile = setup_result["customer_profile"]
        intent         = setup_result["intent"]
        people         = setup_result["people"]
        llm_history    = setup_result["llm_history"]
        tool_call      = setup_result["tool_call"]

        if setup_result.get("commerce_events"):
            for event in setup_result["commerce_events"]:
                yield event
            return

        tool_name = tool_call.tool_name
        tool_args = self._enrich_tool_args(tool_name, tool_call.tool_args, slots, request.filters)

        # ── Shortcut responses (stream word-by-word for typewriter effect) ─
        if tool_name == "clarify_question":
            q = tool_args.get("question", "Could you tell me a bit more?")
            async for event in _stream_words(q):
                yield event
            await self._persist_shortcut(session, request, q, intent, t_start)
            suggestions = await self._generate_suggestions_only(request.message, q)
            yield _sse({"type": "done", "message_id": "", "answer_html": q,
                        "cited_products": [], "suggestions": suggestions})
            return

        if tool_name == "direct_answer":
            a = tool_args.get("content", "")
            async for event in _stream_words(a):
                yield event
            await self._persist_shortcut(session, request, a, intent, t_start)
            suggestions = await self._generate_suggestions_only(request.message, a)
            yield _sse({"type": "done", "message_id": "", "answer_html": a,
                        "cited_products": [], "suggestions": suggestions})
            return

        # ── Execute tool + build prompt ──────────────────────────────────
        # Send SSE heartbeat comments every 5s while waiting for slow RAG/tool calls.
        # This prevents proxy and browser timeouts from killing the connection.
        try:
            tool_task = asyncio.ensure_future(self._tools.execute(tool_name, tool_args))
            while not tool_task.done():
                await asyncio.sleep(5)
                if not tool_task.done():
                    yield ": heartbeat\n\n"
            tool_result = await tool_task
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
                image_base64=getattr(request, "image_base64", None),
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

        # ── Generate title after 2nd user message ─────────────────────────
        if session.message_count == 4 and not session.title:
            logger.info(f"Triggering title generation for session {session.session_id}, message_count={session.message_count}")
            asyncio.create_task(self._generate_session_title(session.session_id))

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

    async def _run_stream_setup(self, request: "ChatRequest", t_start: float) -> dict:
        """
        Runs all blocking setup work for handle_stream in a single coroutine
        so it can be awaited with a heartbeat loop around it.
        Returns a dict with all needed state, or an early_return dict with pre-built events.
        """
        import json

        def _sse(data: dict) -> str:
            return f"data: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"

        async def _collect_stream_words(text: str) -> list[str]:
            events = []
            words = text.split(" ")
            for i, word in enumerate(words):
                token = word if i == 0 else " " + word
                events.append(_sse({"type": "token", "content": token}))
            return events

        await self._rate_limiter.check(request.customer_id)
        session = await self._resolve_session(request)
        await self._check_session_health(session)

        customer_profile, conversation = await asyncio.gather(
            self._memory.load_customer_profile(session.customer_id),
            self._load_history(session),
        )
        slots = self._memory.load_slots(session)
        shown_products = self._memory.load_shown_products(session)

        # Pre-fill slots for returning customers ONLY after they confirm "for myself"
        if customer_profile and session.message_count > 0:
            msg_lower = request.message.lower()
            _self_signals = ["myself", "for me", "for myself", "me ", "i need", "i want", "i'm looking", "im looking", "my size"]
            _other_signals = ["someone", "someone else", "gift", "for my friend", "for my dad", "for my mom", "for my mum", "for my wife", "for my husband", "for my partner", "for him", "for her"]
            is_for_self = any(s in msg_lower for s in _self_signals)
            is_for_other = any(s in msg_lower for s in _other_signals)
            if is_for_self and not is_for_other:
                slots = self._memory.prefill_slots_from_profile(slots, customer_profile)
                # Never prefill budget — always ask fresh
                slots.budget = None

        guard = self._guardrails.check_input(request.message)
        if not guard.passed:
            safe = guard.safe_response or "I can only help with shopping-related questions."
            events = await _collect_stream_words(safe)
            events.append(_sse({"type": "done", "message_id": "", "answer_html": safe,
                                 "cited_products": [], "suggestions": []}))
            return {"early_return": True, "events": events}

        intent = self._guardrails.classify_intent(request.message)
        slots = self._extract_slots(request.message, slots)
        people = self._memory.extract_people_from_message(request.message)

        # ── Checkout agent mode (streaming) ────────────────────────────
        if self._memory.get_active_agent(session) == "checkout":
            checkout_resp = await self._handle_checkout_mode(
                session=session, request=request,
                customer_profile=customer_profile,
                conversation=conversation, t_start=t_start,
            )
            if checkout_resp is not None:
                answer = checkout_resp.answer or ""
                events = await _collect_stream_words(answer)
                done_event: dict = {
                    "type": "done",
                    "message_id": str(checkout_resp.message_id) if checkout_resp.message_id else "",
                    "session_id": str(session.session_id),
                    "answer_html": answer,
                    "cited_products": [],
                    "suggestions": [],
                }
                if checkout_resp.checkout_action:
                    done_event["checkout_action"] = checkout_resp.checkout_action
                events.append(_sse(done_event))
                return {"early_return": True, "events": events}

        commerce_intent = _classify_commerce_intent(request.message)

        # Enter checkout mode for checkout_initiate (streaming path)
        if commerce_intent == "checkout_initiate":
            commerce_slots = await self._extract_commerce_slots(
                message=request.message, intent=commerce_intent, session=session,
            )
            customer_id_str = str(session.customer_id) if session.customer_id else None
            try:
                service_response = await self._dispatch_commerce_intent(
                    intent=commerce_intent, slots=commerce_slots,
                    customer_id=customer_id_str or "",
                    request_id=str(session.session_id), session=session,
                )
                if service_response.success and service_response.data:
                    cs_id = (
                        service_response.data.get("sessionId")
                        or service_response.data.get("session_id", "")
                    )
                    if session.context is None:
                        session.context = {}
                    session.context["checkout_session_id"] = cs_id
            except Exception as exc:
                logger.warning("chat.checkout_session_create_failed", error=str(exc))

            await self._memory.set_active_agent(session, "checkout")
            checkout_request = ChatRequest(
                message="Customer wants to checkout. Present the order summary.",
                customer_id=request.customer_id,
                session_id=request.session_id,
                channel=request.channel,
            )
            checkout_resp = await self._handle_checkout_mode(
                session=session, request=checkout_request,
                customer_profile=customer_profile,
                conversation=conversation, t_start=t_start,
            )
            if checkout_resp is not None:
                answer = checkout_resp.answer or ""
                events = await _collect_stream_words(answer)
                stream_done: dict = {
                    "type": "done",
                    "message_id": str(checkout_resp.message_id) if checkout_resp.message_id else "",
                    "session_id": str(session.session_id),
                    "answer_html": answer,
                    "cited_products": [],
                    "suggestions": [],
                }
                if checkout_resp.checkout_action:
                    stream_done["checkout_action"] = checkout_resp.checkout_action
                events.append(_sse(stream_done))
                return {"early_return": True, "events": events}

        if commerce_intent:
            commerce_response = await self._handle_commerce_intent(
                commerce_intent=commerce_intent,
                message=request.message,
                session=session,
                request=request,
                slots=slots,
                customer_profile=customer_profile,
                t_start=t_start,
            )
            if commerce_response is not None:
                answer = commerce_response.answer or ""
                events = await _collect_stream_words(answer)
                cited = [p.model_dump() if hasattr(p, "model_dump") else p
                         for p in (commerce_response.cited_products or [])]
                suggestions = [s.model_dump() if hasattr(s, "model_dump") else s
                               for s in (commerce_response.suggestions or [])]
                comm_done: dict = {
                    "type": "done",
                    "message_id": str(commerce_response.message_id) if commerce_response.message_id else "",
                    "session_id": str(session.session_id),
                    "answer_html": answer,
                    "cited_products": cited,
                    "suggestions": suggestions,
                }
                if commerce_response.continue_url:
                    comm_done["continue_url"] = commerce_response.continue_url
                if commerce_response.checkout_data:
                    comm_done["checkout_data"] = commerce_response.checkout_data
                if commerce_response.cart_data:
                    comm_done["cart_data"] = commerce_response.cart_data
                if commerce_response.order_history_data:
                    comm_done["order_history_data"] = commerce_response.order_history_data
                if commerce_response.checkout_action:
                    comm_done["checkout_action"] = commerce_response.checkout_action
                events.append(_sse(comm_done))
                return {"early_return": True, "events": events}

        skill_ctx = SkillContext(
            message=request.message, intent=intent, slots=slots,
            customer_profile=customer_profile,
            session_context=session.context or {},
            turn_count=session.message_count,
        )
        skill_result = self._skills.resolve(skill_ctx)

        slot_status = self._build_slot_status(slots)
        tool_system_prompt = TOOL_SELECTION_PROMPT + "\n\n" + slot_status
        if skill_result.prompt_addon:
            tool_system_prompt += "\n\n" + skill_result.prompt_addon
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
            image_base64=getattr(request, "image_base64", None),
        )

        return {
            "early_return": False,
            "session": session,
            "conversation": conversation,
            "slots": slots,
            "shown_products": shown_products,
            "customer_profile": customer_profile,
            "intent": intent,
            "people": people,
            "llm_history": llm_history,
            "tool_call": tool_call,
        }

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
                s("Shopping for myself", "I'm shopping for myself"),
                s("For someone else", "I'm looking for someone else"),
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

    def _build_slot_status(self, slots: SlotState) -> str:
        """
        Build a human-readable summary of collected slots for the LLM.
        Tells the LLM what's been gathered and whether it's enough to search.
        """
        br = business_rules()
        unlimited = br["budget"]["unlimited_sentinel"]

        cat = slots.category or slots.use_case or "not yet asked"
        brand = slots.brand if slots.brand and slots.brand.lower() != "any" else (
            "no preference" if slots.brand and slots.brand.lower() == "any" else "not yet asked"
        )
        budget = (
            f"under ${int(slots.budget)}" if slots.budget and slots.budget < unlimited
            else ("no limit" if slots.budget else "not yet asked")
        )
        color = slots.color or "not yet asked"
        size = slots.size or "not yet asked"

        has_type = bool(slots.category or slots.use_case)
        has_brand = bool(slots.brand)
        has_budget = bool(slots.budget)
        has_size = bool(slots.size)
        has_color = bool(slots.color)
        filled_count = sum([has_brand, has_budget, has_size, has_color])
        ready = has_type and filled_count >= 2

        lines = [
            "CUSTOMER PREFERENCES COLLECTED:",
            f"- Type: {cat}",
            f"- Brand: {brand}",
            f"- Budget: {budget}",
            f"- Color: {color}",
            f"- Size: {size}",
        ]

        if ready:
            reasons = []
            if has_type:
                reasons.append("type")
            if has_brand:
                reasons.append("brand")
            if has_budget:
                reasons.append("budget")
            if has_size:
                reasons.append("size")
            if has_color:
                reasons.append("color")
            lines.append(f"→ READY TO SEARCH. You have {' + '.join(reasons)}. Call search_products NOW. Do NOT ask any more questions.")
        else:
            if not has_type:
                lines.append("→ Not enough info yet. Ask what TYPE of shoes they want.")
            elif not has_size or not has_budget:
                lines.append("→ MANDATORY: Ask about SIZE and BUDGET only. Be creative — vary your wording each time, keep it warm and casual. Do NOT mention brand or color yet. Do NOT search yet.")
            elif not has_brand or not has_color:
                lines.append("→ MANDATORY: Ask about BRAND and COLOR only. Be creative — vary your wording each time, keep it warm and casual. Do NOT mention size or budget. Do NOT search yet.")

        return "\n".join(lines)

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

    # ── Checkout agent mode ──────────────────────────────────────────────

    async def _handle_checkout_mode(
        self,
        session: Session,
        request: ChatRequest,
        customer_profile: dict | None,
        conversation: ConversationHistory,
        t_start: float,
    ) -> ChatResponse | None:
        """
        Handle a message while the checkout agent is active.
        Returns ChatResponse if handled, None to fall through.
        """
        # Timeout check — 30 minutes
        entered_at = self._memory.get_checkout_entered_at(session)
        if entered_at and (time.time() - entered_at > 1800):
            await self._memory.set_active_agent(session, None)
            return await self._direct_response(
                session, request,
                "Your checkout session timed out. Your cart is saved for when you're ready!",
                "checkout_timeout", t_start,
            )

        customer_id = str(session.customer_id) if session.customer_id else ""

        # Load checkout context (fresh every turn)
        stripe_service = StripeCustomerService(self._commerce)
        checkout_session_id = (session.context or {}).get("checkout_session_id", "")
        cart_response = await self._commerce.get_checkout_session(checkout_session_id)
        saved_addresses = (customer_profile or {}).get("addresses", [])
        saved_payments = await stripe_service.list_payment_methods(customer_id)

        cart_data = cart_response.data if cart_response.success else {}

        # Build checkout context JSON for the agent
        checkout_context = {
            "cart": {
                "checkout_session_id": checkout_session_id,
                "line_items": cart_data.get("lineItemsSnapshot", []),
                "totals": cart_data.get("totalsSnapshot", {}),
            },
            "customer": {
                "customer_id": customer_id,
                "name": (customer_profile or {}).get("name", ""),
                "email": (customer_profile or {}).get("email", ""),
                "phone": (customer_profile or {}).get("phone", ""),
            },
            "saved_addresses": saved_addresses,
            "saved_payment_methods": saved_payments,
        }

        # Handle __checkout: prefixed messages from frontend card actions
        message = request.message

        # If the message is a checkout trigger (from re-entry or stale session),
        # rewrite it so the agent presents the order summary instead of
        # misinterpreting the product name as a recommendation request
        _checkout_triggers = [
            "checkout", "buy now", "buy it", "buy this", "i want to buy",
            "place order", "purchase", "customer wants to checkout",
        ]
        if any(t in message.lower() for t in _checkout_triggers):
            message = "Customer wants to checkout. Present the order summary."

        checkout_event = None
        if message.startswith("__checkout:"):
            event_type = message.split(":", 1)[1] if ":" in message else ""
            checkout_event = {"event": event_type}
            if request.filters:
                checkout_event.update(request.filters)
            message = f"[System event: {event_type}]"

        # Load checkout agent prompt
        agent_prompt = skill_loader.load_agent("checkout-agent")
        system_prompt = (
            agent_prompt
            + "\n\n## Current Checkout Context\n\n```json\n"
            + json.dumps(checkout_context, indent=2, default=str)
            + "\n```"
        )
        if checkout_event:
            system_prompt += (
                "\n\n## Incoming Event\n\n```json\n"
                + json.dumps(checkout_event, indent=2)
                + "\n```"
            )

        # History
        llm_history = [
            {"role": t["role"], "content": t["content"]}
            for t in conversation.recent_turns[-6:]
        ]

        # LLM tool decision with checkout tools
        try:
            tool_call = await self._llm.decide_tool(
                system_prompt=system_prompt,
                user_message=message,
                history=llm_history,
                tools=CHECKOUT_TOOL_DEFINITIONS,
            )
        except LLMError:
            return await self._error_response(session, request, t_start)

        # Execute checkout tool
        checkout_tools = CheckoutToolRegistry(
            commerce_client=self._commerce,
            customer_repo=self._customer_repo,
            stripe_service=stripe_service,
            customer_id=customer_id,
            checkout_session_id=checkout_session_id,
        )
        tool_result = await checkout_tools.execute(tool_call.tool_name, tool_call.tool_args)

        # Handle exit_checkout — clear mode
        if tool_call.tool_name == "exit_checkout":
            await self._memory.set_active_agent(session, None)

        # Log checkout tool failures but DON'T auto-exit — let the agent handle it.
        # The agent prompt knows how to offer alternatives on failure.
        if not tool_result.success and tool_call.tool_name != "exit_checkout":
            logger.warning(
                "chat.checkout_tool_failed",
                tool=tool_call.tool_name,
                error=tool_result.summary,
            )

        # Generate response with tool result context
        try:
            llm_result = await self._llm.generate(
                system_prompt=system_prompt,
                user_message=message,
                history=llm_history,
                tool_result_summary=tool_result.summary,
                tool_name=tool_call.tool_name,
            )
        except LLMError:
            return await self._error_response(session, request, t_start)

        # Build response
        response = await self._direct_response(
            session, request, llm_result.content,
            f"checkout_{tool_call.tool_name}", t_start,
        )

        # Attach checkout_action for frontend SSE
        if tool_result.checkout_action:
            response.checkout_action = {
                "action": tool_result.checkout_action,
                **tool_result.data,
            }

        return response

    # ── Instant response builders ─────────────────────────────────────────

    async def _handle_commerce_intent(
        self,
        commerce_intent: str,
        message: str,
        session: Session,
        request: ChatRequest,
        slots: SlotState,
        customer_profile: dict | None = None,
        t_start: float = 0.0,
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
                session=session,
            )
        except Exception as exc:
            logger.warning(
                "chat.commerce_dispatch_failed",
                intent=commerce_intent,
                error=str(exc),
            )
            return await self._error_response(session, request, t_start)

        # ── Format response ───────────────────────────────────────────────
        answer = self._format_commerce_response(commerce_intent, service_response, customer_profile)
        response = await self._direct_response(session, request, answer, commerce_intent, t_start)

        # Attach checkout metadata for the frontend
        if service_response.requires_escalation and service_response.continue_url:
            response.continue_url = service_response.continue_url
        if service_response.data:
            line_items = (
                service_response.data.get("lineItemsSnapshot")
                or service_response.data.get("line_items_snapshot", [])
            )
            totals = (
                service_response.data.get("totalsSnapshot")
                or service_response.data.get("totals_snapshot", {})
            )
            # Normalize totals to snake_case for frontend
            if totals and isinstance(totals, dict):
                totals = {
                    "subtotal_cents": totals.get("subtotal_cents") or totals.get("subtotalCents", 0),
                    "tax_cents": totals.get("tax_cents") or totals.get("taxCents", 0),
                    "grand_total_cents": totals.get("grand_total_cents") or totals.get("grandTotalCents", 0),
                }
            session_id = (
                service_response.data.get("sessionId")
                or service_response.data.get("session_id", "")
            )

            if commerce_intent == "view_cart":
                # Attach cart_data for view_cart intent (renders CartPanel in frontend)
                if (
                    service_response.success
                    and service_response.data.get("message") != "empty_cart"
                    and (line_items or totals)
                ):
                    cart_data: dict = {
                        "line_items": line_items,
                        "totals": totals,
                        "checkout_session_id": session_id,
                    }
                    response.cart_data = cart_data
            else:
                checkout_data: dict = {}
                if line_items or totals:
                    checkout_data["line_items"] = line_items
                    checkout_data["totals"] = totals
                    checkout_data["checkout_session_id"] = session_id

                    # Attach saved addresses from customer profile
                    if customer_profile:
                        saved_addresses = customer_profile.get("addresses", [])
                        if saved_addresses:
                            checkout_data["saved_addresses"] = saved_addresses

                    response.checkout_data = checkout_data

        # Attach order_history_data for order_history intent
        if commerce_intent == "order_history" and service_response.success:
            response.order_history_data = {
                "orders": service_response.data.get("orders", []) if service_response.data else [],
                "next_cursor": service_response.data.get("nextCursor") if service_response.data else None,
            }

        return response

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

        # Extract quantity — only when number appears in a quantity context
        # e.g. "2 pairs", "buy 3", "quantity 5", "add 2 of", "one pair"
        # Avoids matching numbers in product names like "Adispree 5.0 M"
        word_to_num = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }
        qty_patterns = [
            r'(?:buy|add|order|get|want)\s+(\d+)\b',  # "buy 3", "add 2"
            r'(\d+)\s+(?:pair|pairs|item|items|piece|pieces|unit|units|of\s)',  # "2 pairs"
            r'quantity\s*[:=]?\s*(\d+)',  # "quantity: 3"
            r'\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:pair|pairs|item|items|piece|pieces)',
        ]
        for pattern in qty_patterns:
            qty_match = re.search(pattern, msg)
            if qty_match:
                raw = qty_match.group(1)
                slots["quantity"] = word_to_num.get(raw, int(raw) if raw.isdigit() else 1)
                break

        # Resolve product reference via RAG if needed
        if intent in ("add_to_cart", "remove_from_cart", "checkout_initiate") and "product_id" not in slots:
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
            elif is_ambiguous or intent in ("add_to_cart", "checkout_initiate"):
                # Resolve via RAG — use the message as the search query
                chunks = await self._rag.retrieve(
                    query=message,
                    filters={"doc_type": "product"},
                    top_k=1,
                    request_id=None,
                )
                if chunks:
                    slots["product_id"] = chunks[0].product_id
                    # Extract clean product name from RAG content
                    raw = chunks[0].content
                    name_match = re.search(r'Product_name:\s*(.+?)(?:\n|$)', raw)
                    if name_match:
                        slots["_resolved_product_name"] = name_match.group(1).strip()
                    else:
                        # Fallback: use title or first 80 chars
                        slots["_resolved_product_name"] = getattr(chunks[0], 'title', raw[:80])
                    # Store price in paise (×100) from metadata
                    raw_price = chunks[0].metadata.get("price")
                    if raw_price is not None:
                        slots["_resolved_product_price_paise"] = int(float(raw_price) * 100)

        # For checkout_initiate, line_items come from the session context (cart)
        # OR from a product resolved via RAG in this same message
        if intent == "checkout_initiate":
            cart = session.context.get("cart", {})
            line_items = cart.get("line_items", [])
            if line_items:
                slots["line_items"] = line_items
            elif slots.get("product_id"):
                # Build line_items from the product resolved in this message
                slots["line_items"] = [{
                    "item": {
                        "id": slots["product_id"],
                        "title": slots.get("_resolved_product_name", slots["product_id"]),
                        "price": max(1, slots.get("_resolved_product_price_paise", 0)),
                    },
                    "quantity": slots.get("quantity", 1),
                }]

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
        session: "Session | None" = None,
    ):
        """Route a validated commerce intent to the CommerceClient."""
        from app.clients.commerce_client import CommerceResponse

        if intent == "add_to_cart":
            line_item = {
                "item": {
                    "id": slots["product_id"],
                    "title": slots.get("_resolved_product_name", slots["product_id"]),
                    "price": max(1, slots.get("_resolved_product_price_paise", 0)),
                },
                "quantity": slots.get("quantity", 1),
            }
            checkout_session_id = (
                session.context.get("cart", {}).get("checkout_session_id")
                if session is not None
                else None
            )
            if checkout_session_id:
                # Verify the existing session isn't already completed/canceled before reusing
                existing = await self._commerce.get_checkout_session(
                    session_id=checkout_session_id,
                    request_id=request_id,
                )
                existing_status = (
                    existing.data.get("ucpStatus") or existing.data.get("ucp_status", "")
                ) if existing.success and existing.data else ""
                if existing_status in ("completed", "canceled", "COMPLETED", "CANCELED"):
                    # Old session is done — clear it and create a new one
                    if session is not None:
                        session.context.get("cart", {}).pop("checkout_session_id", None)
                    checkout_session_id = None

            if checkout_session_id:
                return await self._commerce.update_checkout_session(
                    session_id=checkout_session_id,
                    line_items=[line_item],
                    request_id=request_id,
                )
            else:
                result = await self._commerce.create_checkout_session(
                    customer_id=customer_id,
                    line_items=[line_item],
                    request_id=request_id,
                )
                if result.success and session is not None:
                    session.context.setdefault("cart", {})["checkout_session_id"] = (
                        result.data.get("sessionId") or result.data.get("session_id", "")
                    )
                return result

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
            checkout_session_id = (
                session.context.get("cart", {}).get("checkout_session_id")
                if session is not None
                else None
            )
            if not checkout_session_id:
                return CommerceResponse(success=True, data={"message": "empty_cart"})
            return await self._commerce.get_checkout_session(
                session_id=checkout_session_id,
                request_id=request_id,
            )

        elif intent == "checkout_initiate":
            line_items = slots.get("line_items", [])
            if not line_items:
                # No items to checkout — ask the user to pick a product first
                return CommerceResponse(
                    success=True,
                    data={"message": "no_items_to_checkout"},
                )
            return await self._commerce.create_checkout_session(
                customer_id=customer_id,
                line_items=line_items,
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

    def _format_commerce_response(
        self, intent: str, response, customer_profile: dict | None = None,
    ) -> str:
        """
        Format a CommerceResponse into a natural language reply.
        When requires_escalation, format continue_url as a clickable markdown link.
        """
        # Handle requires_escalation — the frontend will show the checkout modal
        if response.requires_escalation:
            data = response.data or {}
            line_items = (
                data.get("lineItemsSnapshot")
                or data.get("line_items_snapshot", [])
            )
            items_desc = []
            for li in line_items:
                item = li.get("item", {})
                title = item.get("title", "Item")
                qty = li.get("quantity", 1)
                items_desc.append(f"{title} x {qty}")
            items_summary = ", ".join(items_desc) if items_desc else "your selected items"

            # Mention saved address if available
            address_hint = ""
            if customer_profile:
                saved_addresses = customer_profile.get("addresses", [])
                if saved_addresses:
                    default_addr = next(
                        (a for a in saved_addresses if a.get("is_default")),
                        saved_addresses[0],
                    )
                    city = default_addr.get("city", "")
                    label = default_addr.get("label", "")
                    addr_desc = f"{label} ({city})" if label and city else city or label or "your saved address"
                    address_hint = (
                        f" I see you have a saved delivery address: {addr_desc}."
                        " You can use it or enter a new one in the checkout."
                    )

            return (
                f"Great! I've prepared your checkout for {items_summary}."
                f"{address_hint} "
                "Click the button below to complete your purchase."
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
            if data.get("message") == "no_items_to_checkout":
                return (
                    "You don't have any items to checkout yet. "
                    "Would you like me to help you find a product first?"
                )
            status = (
                data.get("ucpStatus")
                or data.get("ucp_status")
                or data.get("status", "")
            )
            session_id = data.get("sessionId") or data.get("session_id", "")
            line_items = data.get("lineItemsSnapshot") or data.get("line_items_snapshot", [])
            totals = data.get("totalsSnapshot") or data.get("totals_snapshot", {})

            if status == "incomplete":
                # Build a nice summary of what's being purchased
                items_desc = []
                for li in line_items:
                    item = li.get("item", {})
                    title = item.get("title", "Item")
                    qty = li.get("quantity", 1)
                    items_desc.append(f"{title} × {qty}")
                items_summary = ", ".join(items_desc) if items_desc else "your selected items"
                grand_total = totals.get("grand_total_cents", 0)
                return (
                    f"I've started your checkout for {items_summary}. "
                    "Please provide your shipping address and payment details to complete your purchase."
                )
            return f"Checkout session created successfully! Your session ID is {session_id}."

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

    async def _generate_session_title(self, session_id: uuid.UUID) -> None:
        """
        Generate a short title for the session using LLM.
        Called in background after 2nd user message.
        """
        from app.db.session import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as db:
                session_repo = SessionRepository(db)
                message_repo = MessageRepository(db)
                
                # Get first 2 user messages
                messages = await message_repo.get_recent_turns(session_id, limit=4)
                if not messages:
                    return
                
                # Build conversation context
                conversation = "\n".join([
                    f"{'User' if m.role == MessageRole.USER else 'Assistant'}: {m.content}"
                    for m in messages[:4]
                ])
                
                # Ask LLM for a short title
                prompt = f"""Based on this conversation, generate a short 3-5 word title that summarizes what the user is looking for.

Conversation:
{conversation}

Return ONLY the title, nothing else. Examples:
- "Casual sneakers for summer"
- "Running shoes comparison"
- "Formal shoes under $100"
- "Nike Air Max review"

Title:"""
                
                try:
                    title_response = await self._llm.generate(
                        system_prompt="You are a helpful assistant that creates short, descriptive titles.",
                        user_message=prompt,
                        temperature=0.3,
                        max_tokens=20,
                    )
                    title = title_response.content.strip().strip('"').strip("'")
                    
                    # Update session with title
                    await session_repo.update_title(session_id, title)
                    await db.commit()
                    logger.info(f"Generated title for session {session_id}: {title}")
                except Exception as e:
                    logger.warning(f"Failed to generate title for session {session_id}: {e}")
        except Exception as e:
            logger.error(f"Error in _generate_session_title: {e}")


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
