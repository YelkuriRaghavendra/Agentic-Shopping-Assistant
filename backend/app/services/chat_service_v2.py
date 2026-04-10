"""
Chat service v2 — thin wrapper around LangGraph graph.

Replaces the 2,274-line monolithic orchestrator with a ~150-line wrapper
that delegates all agent logic to the LangGraph state graph.
"""

import json
import time

from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dto.chat_dto import ChatRequest, ChatResponse, ProductCardDTO
from app.core.logging import get_logger
from app.db.models.enums.message_enums import GuardrailStatus, MessageRole
from app.db.models.enums.session_enums import SessionStatus
from app.db.models.session import Session
from app.db.repositories import CustomerRepository, MessageRepository, SessionRepository
from app.services.rate_limiter_service import RateLimiterService

logger = get_logger(__name__)


class ChatServiceV2:
    """Thin wrapper that delegates all agent logic to the LangGraph state graph."""

    def __init__(self, db: AsyncSession, graph, rate_limiter: RateLimiterService):
        self._db = db
        self._graph = graph
        self._rate_limiter = rate_limiter
        self._session_repo = SessionRepository(db)
        self._customer_repo = CustomerRepository(db)
        self._message_repo = MessageRepository(db)

    # ── Sync (non-streaming) handler ────────────────────────────────────────

    async def handle(self, request: ChatRequest) -> ChatResponse:
        t_start = time.monotonic()

        # 1. Rate limit
        await self._rate_limiter.check(request.customer_id)

        # 2. Resolve session
        session = await self._resolve_session(request)

        # 3. Load customer profile
        customer_profile = {}
        if session.customer_id:
            customer = await self._customer_repo.get_by_id(session.customer_id)
            if customer:
                customer_profile = customer.profile or {}

        # 4. Load conversation history + build input state
        history = await self._load_history_messages(session.session_id)
        input_state = self._build_input_state(request, session, customer_profile, history)

        # 5. Invoke graph
        config = {"configurable": {"thread_id": str(session.session_id)}}
        result = await self._graph.ainvoke(input_state, config)

        # 6. Persist messages
        await self._message_repo.create(
            session_id=session.session_id,
            role=MessageRole.USER,
            content=request.message,
            intent=result.get("intent", ""),
            guardrail_status=GuardrailStatus.PASSED,
        )

        agent_response = result.get("agent_response", "")
        guard_status = (
            GuardrailStatus.PASSED
            if result.get("guardrail_status") == "passed"
            else GuardrailStatus.WARNED
        )
        cited_products_raw = result.get("cited_products", [])

        bot_msg = await self._message_repo.create(
            session_id=session.session_id,
            role=MessageRole.ASSISTANT,
            content=agent_response,
            intent=result.get("intent", ""),
            guardrail_status=guard_status,
            cited_products=cited_products_raw,
            latency_ms=int((time.monotonic() - t_start) * 1000),
        )

        est_tokens = len(agent_response) // 4
        await self._session_repo.increment_counters(
            session.session_id,
            turn_delta=2,
            token_delta=est_tokens,
        )
        await self._db.commit()

        # 7. Build response
        cited_products = [
            ProductCardDTO(**p) if isinstance(p, dict) else p for p in cited_products_raw
        ]
        suggestions = result.get("suggestions", [])
        latency_ms = int((time.monotonic() - t_start) * 1000)

        return ChatResponse(
            message_id=bot_msg.message_id,
            session_id=session.session_id,
            answer=agent_response,
            answer_html=agent_response,  # citations already processed by graph node
            cited_products=cited_products,
            suggestions=suggestions,
            intent=result.get("intent", ""),
            guardrail_status=guard_status,
            blocked=result.get("guardrail_status") == "blocked",
            latency_ms=latency_ms,
            tokens_used=est_tokens,
        )

    # ── Streaming handler ───────────────────────────────────────────────────

    async def handle_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Streaming version using graph.astream_events."""
        t_start = time.monotonic()

        def _sse(data: dict) -> str:
            return f"data: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"

        yield ": heartbeat\n\n"

        try:
            await self._rate_limiter.check(request.customer_id)
            session = await self._resolve_session(request)

            customer_profile = {}
            if session.customer_id:
                customer = await self._customer_repo.get_by_id(session.customer_id)
                if customer:
                    customer_profile = customer.profile or {}

            history = await self._load_history_messages(session.session_id)
            input_state = self._build_input_state(request, session, customer_profile, history)
            config = {"configurable": {"thread_id": str(session.session_id)}}

            full_response = ""
            final_state = {}
            active_agent = None
            supervisor_done = False

            async for event in self._graph.astream_events(input_state, config, version="v2"):
                kind = event.get("event", "")
                tags = event.get("tags", [])

                # Track when supervisor finishes (so we know subsequent LLM calls are from agents)
                if kind == "on_chain_end" and event.get("name") == "supervisor":
                    supervisor_done = True

                # Agent status events
                if kind == "on_chain_start":
                    name = event.get("name", "")
                    if name in (
                        "shopping",
                        "style_advisor",
                        "gift_finder",
                        "support",
                        "checkout",
                    ):
                        active_agent = name
                        yield _sse({
                            "type": "agent_status",
                            "agent": name,
                            "status": "Working on your request...",
                        })

                # Token streaming — only from domain agents, not supervisor
                if kind == "on_chat_model_stream" and supervisor_done:
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        full_response += chunk.content
                        yield _sse({"type": "token", "content": chunk.content})

                # Chain end — capture final state
                if kind == "on_chain_end" and event.get("name") == "LangGraph":
                    final_state = event.get("data", {}).get("output", {})

            # Persist messages
            await self._message_repo.create(
                session_id=session.session_id,
                role=MessageRole.USER,
                content=request.message,
                intent=final_state.get("intent", ""),
                guardrail_status=GuardrailStatus.PASSED,
            )

            agent_response = final_state.get("agent_response", full_response)
            cited_products_raw = final_state.get("cited_products", [])

            bot_msg = await self._message_repo.create(
                session_id=session.session_id,
                role=MessageRole.ASSISTANT,
                content=agent_response,
                intent=final_state.get("intent", ""),
                guardrail_status=GuardrailStatus.PASSED,
                cited_products=cited_products_raw,
                latency_ms=int((time.monotonic() - t_start) * 1000),
            )

            await self._session_repo.increment_counters(
                session.session_id,
                turn_delta=2,
                token_delta=len(agent_response) // 4,
            )
            await self._db.commit()

            yield _sse({
                "type": "done",
                "message_id": str(bot_msg.message_id),
                "session_id": str(session.session_id),
                "answer_html": agent_response,
                "cited_products": cited_products_raw,
                "suggestions": final_state.get("suggestions", []),
                "intent": final_state.get("intent", ""),
            })

        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            logger.error("stream.failed", error=str(exc), traceback=tb)
            yield _sse({"type": "error", "content": f"Error: {exc}"})

    # ── Private helpers ─────────────────────────────────────────────────────

    async def _resolve_session(self, request: ChatRequest) -> Session:
        """Find active session or create a new one."""
        if request.session_id:
            session = await self._session_repo.get_by_id(request.session_id)
            if session and session.status == SessionStatus.ACTIVE:
                return session

        # Find active session for customer
        if request.customer_id:
            sessions = await self._session_repo.get_sessions_for_customer(request.customer_id)
            for s in sessions:
                if s.status == SessionStatus.ACTIVE:
                    return s

        # Create new session
        session = await self._session_repo.create(
            customer_id=request.customer_id,
            channel=request.channel or "WEB",
        )
        await self._db.commit()
        return session

    async def _load_history_messages(self, session_id) -> list:
        """Load recent turns from DB as LangChain messages."""
        recent = await self._message_repo.get_recent_turns(session_id, limit=12)
        messages = []
        for msg in recent:
            if msg.role.value == "USER":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role.value == "ASSISTANT":
                messages.append(AIMessage(content=msg.content))
        return messages

    def _build_input_state(
        self, request: ChatRequest, session: Session, customer_profile: dict,
        history_messages: list | None = None,
    ) -> dict:
        """Construct the initial AgentState dict for graph invocation."""
        ctx = session.context or {}
        # Prepend conversation history + current message
        messages = list(history_messages or [])
        messages.append(HumanMessage(content=request.message))
        return {
            "messages": messages,
            "customer_id": str(session.customer_id) if session.customer_id else None,
            "customer_profile": customer_profile,
            "slots": ctx.get("slots", {}),
            "shown_products": ctx.get("shown_products", []),
            "checkout_session_id": ctx.get("checkout_session_id"),
            "checkout_state": ctx.get("checkout_state", {}),
            "current_agent": ctx.get("active_agent"),
            "intent": None,
            "agent_response": None,
            "retrieved_chunks": [],
            "tool_results": [],
            "cited_products": [],
            "suggestions": [],
            "guardrail_status": "pending",
            "stream_events": [],
        }
