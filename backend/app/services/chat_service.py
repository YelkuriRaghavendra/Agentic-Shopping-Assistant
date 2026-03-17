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
  8.  LLM decides which tool to call
  9.  Execute tool (RAG, order lookup, policy, etc.)
  10. Build prompt (all memory layers injected)
  11. Generate LLM response
  12. Output guardrails
  13. Citation processing
  14. Persist messages + update memory
  15. Trigger background tasks (profile update, summarisation)
  16. Return structured response

This service knows nothing about HTTP — no FastAPI, no Request, no Response.
"""

import asyncio
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dto.chat_dto import ChatRequest, ChatResponse, ProductCardDTO
from app.clients.llm_client import LLMClient, ToolCall
from app.clients.rag_client import RAGClient
from app.core.config import get_settings
from app.core.exceptions import (
    SessionNotFoundError,
    SessionExpiredError,
    SessionInactiveError,
    TokenBudgetExceededError,
    LLMError,
)
from app.db.models.models import Session
from app.db.repositories import (
    SessionRepository,
    CustomerRepository,
    MessageRepository,
)
from app.services.citation_service import CitationService
from app.services.guardrails_service import GuardrailsService
from app.services.memory_service import MemoryService, SlotState, ConversationHistory
from app.services.prompt_builder_service import PromptBuilderService
from app.services.rate_limiter_service import RateLimiterService
from app.services.suggestion_service import SuggestionService
from app.services.tool_registry import ToolRegistry, TOOL_DEFINITIONS
from app.services.skills.skill_registry import SkillRegistry
from app.services.skills.base_skill import SkillContext
from app.services.skills.prompts import TOOL_SELECTION_PROMPT
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# LLM prompt that teaches the agent when to ask vs when to search
# Tool selection prompt lives in app/services/skills/prompts.py → TOOL_SELECTION_PROMPT


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
        suggestions:   SuggestionService,
        skills:        SkillRegistry,
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
        self._suggestions  = suggestions
        self._skills       = skills

        self._session_repo  = SessionRepository(db)
        self._customer_repo = CustomerRepository(db)
        self._message_repo  = MessageRepository(db)

    async def handle(self, request: ChatRequest) -> ChatResponse:
        t_start = time.monotonic()

        # ── 1. Rate limit ─────────────────────────────────────────────────
        self._rate_limiter.check(request.customer_id)

        # ── 2. Resolve session ────────────────────────────────────────────
        session = await self._resolve_session(request)

        # ── 3. Session health ─────────────────────────────────────────────
        await self._check_session_health(session)

        # ── 4. Load memory ────────────────────────────────────────────────
        customer_profile = await self._memory.load_customer_profile(session.customer_id)
        slots            = self._memory.load_slots(session)
        shown_products   = self._memory.load_shown_products(session)
        conversation     = await self._load_history(session)

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

        llm_history = [
            {"role": t["role"], "content": t["content"]}
            for t in conversation.recent_turns[-6:]
        ]
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

        logger.info("chat.tool_selected", session_id=str(session.id), tool=tool_name, intent=intent)

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
        system_prompt, user_prompt, citation_map = self._prompt.build(
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
            [c.title for c in tool_result.retrieved_chunks],
        )
        final_text = llm_result.content
        guard_status = "passed"
        if not out_guard.passed:
            final_text   = out_guard.safe_response or final_text
            guard_status = "warned"

        # ── 14. Citation processing ────────────────────────────────────────
        answer, answer_html, cited_products = self._citations.process(
            final_text, citation_map
        )

        # ── 15. Persist everything ────────────────────────────────────────
        await self._message_repo.create(
            session_id=session.id,
            role="user",
            content=request.message,
            intent=intent,
            guardrail_status="passed",
        )
        bot_msg = await self._message_repo.create(
            session_id=session.id,
            role="assistant",
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
            session_id=session.id,
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
            session_id=session.id,
            customer_id=session.customer_id,
            slots=slots,
            cited_products=cited_products,
            intent=intent,
            people=people,
        )

        # ── 17. Generate suggestions ─────────────────────────────────────
        suggestion_response = self._suggestions.generate(
            intent=intent,
            slots=slots,
            cited_products=cited_products,
            blocked=False,
            last_user_message=request.message,
        )

        latency_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "chat.complete",
            session_id=str(session.id),
            tool=tool_name,
            latency_ms=latency_ms,
            citations=len(cited_products),
            suggestions=len(suggestion_response.chips),
            skills=skill_result.metadata.get("active_skills", []),
            tokens=llm_result.input_tokens + llm_result.output_tokens,
        )

        return ChatResponse(
            message_id=bot_msg.id,
            session_id=session.id,
            answer=answer,
            answer_html=answer_html,
            cited_products=cited_products,
            suggestions=[c.model_dump() for c in suggestion_response.chips],
            intent=intent,
            guardrail_status=guard_status,
            blocked=False,
            latency_ms=latency_ms,
            tokens_used=llm_result.input_tokens + llm_result.output_tokens,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

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
                session_id=str(session.id),
                customer_id=str(request.customer_id) if request.customer_id else "guest",
            )
        return session

    async def _check_session_health(self, session: Session) -> None:
        if session.status == "expired":
            raise SessionExpiredError()
        if session.status != "active":
            raise SessionInactiveError(f"Session is {session.status}.")
        if session.total_tokens >= settings.SESSION_TOKEN_BUDGET:
            raise TokenBudgetExceededError()

    async def _load_history(self, session: Session) -> ConversationHistory:
        messages = await self._message_repo.get_recent_turns(
            session_id=session.id,
            limit=settings.CONVERSATION_WINDOW_TURNS * 2,
        )
        return ConversationHistory(
            recent_turns=[
                {"role": m.role, "content": m.content}
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
        import re
        from app.config.loader import business_rules

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

        from app.config.loader import business_rules
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
        people: list | None = None,
    ) -> None:
        """Schedule background work. Each task creates its own DB session."""
        if customer_id:
            asyncio.create_task(
                _bg_update_profile(customer_id, slots, cited_products, intent, people or [])
            )
        asyncio.create_task(_bg_summarise(session_id))

    # ── Instant response builders ─────────────────────────────────────────

    async def _blocked_response(
        self, session, request, reason, safe_response, t_start
    ) -> ChatResponse:
        await self._message_repo.create(
            session_id=session.id, role="user", content=request.message,
            intent="blocked", guardrail_status="blocked", guardrail_reason=reason,
        )
        bot_msg = await self._message_repo.create(
            session_id=session.id, role="assistant", content=safe_response,
            guardrail_status="blocked",
        )
        await self._session_repo.increment_counters(session.id, turn_delta=2)
        await self._db.commit()
        _, answer_html, _ = self._citations.process(safe_response, {})
        return ChatResponse(
            message_id=bot_msg.id, session_id=session.id,
            answer=safe_response, answer_html=answer_html, cited_products=[],
            intent="blocked", guardrail_status="blocked", blocked=True,
            latency_ms=int((time.monotonic() - t_start) * 1000), tokens_used=0,
        )

    async def _question_response(
        self, session, request, question, intent, t_start
    ) -> ChatResponse:
        """Return clarifying question — zero LLM cost."""
        await self._message_repo.create(
            session_id=session.id, role="user", content=request.message,
            intent=intent, guardrail_status="passed",
        )
        bot_msg = await self._message_repo.create(
            session_id=session.id, role="assistant", content=question,
            intent="slot_filling", guardrail_status="passed", llm_model="rule_based",
        )
        await self._session_repo.increment_counters(session.id, turn_delta=2)
        await self._db.commit()
        _, answer_html, _ = self._citations.process(question, {})
        return ChatResponse(
            message_id=bot_msg.id, session_id=session.id,
            answer=question, answer_html=answer_html, cited_products=[],
            suggestions=[],
            intent="slot_filling", guardrail_status="passed", blocked=False,
            latency_ms=int((time.monotonic() - t_start) * 1000), tokens_used=0,
        )

    async def _direct_response(
        self, session, request, answer, intent, t_start
    ) -> ChatResponse:
        await self._message_repo.create(
            session_id=session.id, role="user", content=request.message,
            intent=intent, guardrail_status="passed",
        )
        bot_msg = await self._message_repo.create(
            session_id=session.id, role="assistant", content=answer,
            intent=intent, guardrail_status="passed", llm_model="direct",
        )
        await self._session_repo.increment_counters(session.id, turn_delta=2)
        await self._db.commit()
        _, answer_html, _ = self._citations.process(answer, {})
        return ChatResponse(
            message_id=bot_msg.id, session_id=session.id,
            answer=answer, answer_html=answer_html, cited_products=[],
            suggestions=[],
            intent=intent, guardrail_status="passed", blocked=False,
            latency_ms=int((time.monotonic() - t_start) * 1000), tokens_used=0,
        )

    async def _error_response(self, session, request, t_start) -> ChatResponse:
        msg = "I'm having a bit of trouble right now. Please try again in a moment."
        await self._message_repo.create(
            session_id=session.id, role="user", content=request.message, intent="error",
        )
        bot_msg = await self._message_repo.create(
            session_id=session.id, role="assistant", content=msg,
            guardrail_status="passed", llm_model="fallback",
        )
        await self._session_repo.increment_counters(session.id, turn_delta=2)
        await self._db.commit()
        _, answer_html, _ = self._citations.process(msg, {})
        return ChatResponse(
            message_id=bot_msg.id, session_id=session.id,
            answer=msg, answer_html=answer_html, cited_products=[],
            suggestions=[],
            intent="error", guardrail_status="passed", blocked=False,
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
    people: list | None = None,
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
                f"{'Customer' if m.role == 'user' else 'Bot'}: {m.content}"
                for m in messages[:-12]   # summarise older turns, keep last 6
            )

            llm    = LLMClient()
            summary = await llm.summarise(transcript)

            memory = MemoryService(session_repo=sess_r, customer_repo=CustomerRepository(db))
            await memory.persist_summary(session_id, summary)
            await db.commit()
    except Exception as exc:
        logger.warning("bg_summarise.failed", session_id=str(session_id), error=str(exc))
