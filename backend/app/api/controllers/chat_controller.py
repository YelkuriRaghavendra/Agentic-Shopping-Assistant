"""
Chat controller.

HTTP boundary layer only:
  - Receive HTTP request
  - Call the service
  - Return HTTP response

No business logic here.
No SQL here.
No LLM calls here.
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dto.chat_dto import (
    ChatRequest, ChatResponse,
    CustomerCreateRequest, CustomerResponse,
    SessionResponse, SessionCreateRequest,
    MessageHistoryResponse, MessageResponse,
    FeedbackRequest, FeedbackResponse,
)
from app.core.exceptions import (
    ChatServiceError,
    NotFoundError,
    RateLimitError,
    DomainValidationError,
    TokenBudgetExceededError,
)
from app.core.logging import get_logger
from app.db.session import get_db
from app.db.repositories import (
    CustomerRepository,
    SessionRepository,
    MessageRepository,
)
from app.clients.llm_client import LLMClient
from app.clients.rag_client import RAGClient
from app.clients.commerce_client import CommerceClient
from app.services.chat_service import ChatService
from app.services.feature_flag_service import FeatureFlagService
from app.services.guardrails_service import GuardrailsService
from app.services.memory_service import MemoryService
from app.services.prompt_builder_service import PromptBuilderService
from app.services.citation_service import CitationService
from app.services.rate_limiter_service import RateLimiterService
from app.services.tool_registry import ToolRegistry
from app.services.skills.skill_registry import SkillRegistry

import uuid

logger = get_logger(__name__)

# Module-level singletons for stateless services
_llm_client    = LLMClient()
_rag_client    = RAGClient()
_commerce      = CommerceClient()
_feature_flags = FeatureFlagService()
_rate_limiter  = RateLimiterService()
_guardrails    = GuardrailsService()
_prompt        = PromptBuilderService()
_citations     = CitationService()
_skills        = SkillRegistry()


def _make_chat_service(db: AsyncSession) -> ChatService:
    """
    Factory: builds ChatService with all dependencies wired up.
    Called once per request.
    """
    session_repo  = SessionRepository(db)
    customer_repo = CustomerRepository(db)
    return ChatService(
        db=db,
        llm_client=_llm_client,
        rag_client=_rag_client,
        rate_limiter=_rate_limiter,
        guardrails=_guardrails,
        memory=MemoryService(session_repo, customer_repo),
        prompt=_prompt,
        citations=_citations,
        tools=ToolRegistry(_rag_client),
        skills=_skills,
        commerce=_commerce,
        feature_flags=_feature_flags,
    )


def _http_status_for(exc: ChatServiceError) -> int:
    return exc.http_status


class ChatController:
    """
    All chat endpoints.
    Methods map 1:1 to routes registered in routes/v1/chat.py.
    """

    async def send_message(
        self,
        request: ChatRequest,
        db: AsyncSession = Depends(get_db),
    ) -> ChatResponse:
        """
        Main chat endpoint.
        Auto-resolves session — no need to create a session first.
        """
        try:
            svc = _make_chat_service(db)
            return await svc.handle(request)
        except (DomainValidationError, TokenBudgetExceededError) as exc:
            raise HTTPException(
                status_code=exc.http_status,
                detail=exc.message,
            )
        except RateLimitError as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=exc.message,
                headers={"Retry-After": "60"},
            )
        except NotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=exc.message,
            )
        except ChatServiceError as exc:
            logger.error("controller.unexpected_error", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred. Please try again.",
            )

    async def send_message_stream(
        self,
        request: ChatRequest,
        db: AsyncSession = Depends(get_db),
    ) -> StreamingResponse:
        """
        Streaming chat endpoint using Server-Sent Events.
        Streams tokens as they arrive from the LLM.
        """
        svc = _make_chat_service(db)

        async def event_generator():
            try:
                async for event in svc.handle_stream(request):
                    yield event
            except Exception as exc:
                import json
                logger.error("stream.failed", error=str(exc))
                yield f"data: {json.dumps({'type': 'error', 'content': 'An unexpected error occurred.'})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def get_history(
        self,
        session_id: uuid.UUID,
        limit: int = 50,
        before_id: uuid.UUID | None = None,
        db: AsyncSession = Depends(get_db),
    ) -> MessageHistoryResponse:
        """
        Cursor-paginated message history.
        Use returned next_cursor as before_id for the next page.
        """
        repo     = MessageRepository(db)
        messages = await repo.get_page(
            session_id=session_id,
            limit=limit,
            before_id=before_id,
        )
        next_cursor = messages[0].message_id if len(messages) == limit else None
        return MessageHistoryResponse(
            messages=[MessageResponse.model_validate(m) for m in messages],
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
        )

    async def create_session(
        self,
        request: SessionCreateRequest,
        db: AsyncSession = Depends(get_db),
    ) -> SessionResponse:
        """
        Explicitly create a session.
        Most clients don't need this — POST /chat auto-creates sessions.
        Use this if you need the session ID before sending the first message.
        """
        repo    = SessionRepository(db)
        session = await repo.create(
            customer_id=request.customer_id,
            channel=request.channel,
        )
        await db.commit()
        return SessionResponse.model_validate(session)

    async def get_session(
        self,
        session_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
    ) -> SessionResponse:
        repo    = SessionRepository(db)
        session = await repo.get_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        return SessionResponse.model_validate(session)

    async def end_session(
        self,
        session_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
    ) -> SessionResponse:
        repo    = SessionRepository(db)
        session = await repo.end(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        await db.commit()
        return SessionResponse.model_validate(session)

    async def create_customer(
        self,
        request: CustomerCreateRequest,
        db: AsyncSession = Depends(get_db),
    ) -> CustomerResponse:
        repo     = CustomerRepository(db)
        customer = await repo.create(
            external_id=request.external_id,
            email=request.email,
            name=request.name,
            phone=request.phone,
            profile=request.profile,
        )
        await db.commit()
        return CustomerResponse.model_validate(customer)

    async def get_customer_sessions(
        self,
        customer_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
    ) -> list[SessionResponse]:
        """Return all sessions for a customer, newest first."""
        customer_repo = CustomerRepository(db)
        customer = await customer_repo.get_by_id(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found.")
        repo = SessionRepository(db)
        sessions = await repo.get_sessions_for_customer(customer_id)
        return [SessionResponse.model_validate(s) for s in sessions]

    async def get_customer(
        self,
        customer_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
    ) -> CustomerResponse:
        repo     = CustomerRepository(db)
        customer = await repo.get_by_id(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found.")
        return CustomerResponse.model_validate(customer)

    async def update_customer_profile(
        self,
        customer_id: uuid.UUID,
        request: Request,
        db: AsyncSession = Depends(get_db),
    ) -> CustomerResponse:
        """Update customer profile (merge). Used to save addresses, preferences, etc."""
        body = await request.json()
        profile_data = body.get("profile", {})
        if not profile_data:
            raise HTTPException(status_code=400, detail="profile field is required.")
        repo = CustomerRepository(db)
        customer = await repo.get_by_id(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found.")
        await repo.update_profile(customer_id, profile_data)
        await db.commit()
        # Re-fetch to return updated state
        customer = await repo.get_by_id(customer_id)
        return CustomerResponse.model_validate(customer)

    async def add_feedback(
        self,
        session_id: uuid.UUID,
        request: FeedbackRequest,
        db: AsyncSession = Depends(get_db),
    ) -> FeedbackResponse:
        repo = SessionRepository(db)
        # Verify session exists
        session = await repo.get_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        feedback = await repo.add_feedback(
            session_id=session_id,
            rating=request.rating,
            comment=request.comment,
            feedback_type=request.feedback_type,
        )
        await db.commit()
        return FeedbackResponse.model_validate(feedback)


# Singleton controller instance
chat_controller = ChatController()
