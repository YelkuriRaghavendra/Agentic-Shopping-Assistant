"""
Chat controller.

HTTP boundary layer only:
  - Receive HTTP request
  - Call the LangGraph agent
  - Return HTTP response

No business logic here.
No SQL here.
No LLM calls here.
"""

import pathlib

from fastapi import Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dto.chat_dto import (
    ChatRequest, ChatResponse,
    CustomerCreateRequest, CustomerResponse,
    SessionResponse, SessionCreateRequest,
    MessageHistoryResponse, MessageResponse,
    FeedbackRequest, FeedbackResponse,
)
from app.core.logging import get_logger
from app.db.session import get_db
from app.db.repositories import (
    CustomerRepository,
    SessionRepository,
    MessageRepository,
)

import uuid

logger = get_logger(__name__)


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
        Main chat endpoint — powered by LangGraph agent.
        Auto-resolves session — no need to create a session first.
        """
        import time
        from app.graph import create_agent

        agent = create_agent(db)
        result = await agent.ainvoke(
            {"request": request, "t_start": time.monotonic()},
            config={"configurable": {"thread_id": str(request.session_id or "default")}},
        )
        response = result.get("response")
        if not response:
            raise HTTPException(status_code=500, detail="Agent returned no response")
        return response

    async def send_message_stream(
        self,
        request: ChatRequest,
        db: AsyncSession = Depends(get_db),
    ) -> StreamingResponse:
        """
        Streaming chat endpoint using Server-Sent Events.
        Streams tokens via the LangGraph agent.
        """
        from app.graph import stream_graph

        return StreamingResponse(
            stream_graph(request, db),
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


    # ── Image upload ────────────────────────────────────────────────────────────

    UPLOAD_DIR = pathlib.Path("/tmp/vikrai-uploads")
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
    ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
    # Magic-byte signatures for allowed image formats
    MAGIC_BYTES = {
        b"\xff\xd8\xff": "image/jpeg",
        b"\x89PNG": "image/png",      # first 4 bytes: 89 50 4E 47
        b"RIFF": "image/webp",
    }

    async def upload_image(self, file: UploadFile) -> dict:
        """
        Accept a multipart image upload, validate, and persist to disk.
        Returns the public URL for the uploaded file.
        """
        # --- Content-type check ---
        if file.content_type not in self.ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{file.content_type}'. Allowed: jpeg, png, webp.",
            )

        # --- Read file bytes (enforce max size) ---
        data = await file.read()
        if len(data) > self.MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large ({len(data)} bytes). Maximum allowed: {self.MAX_IMAGE_SIZE} bytes (5 MB).",
            )

        # --- Magic-byte validation ---
        valid_magic = False
        for magic, _ in self.MAGIC_BYTES.items():
            if data[:len(magic)] == magic:
                valid_magic = True
                break
        if not valid_magic:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File does not appear to be a valid image (magic bytes check failed).",
            )

        # --- Warn on suspiciously small files ---
        if len(data) < 1024:
            logger.warning(
                "upload.small_file",
                size=len(data),
                content_type=file.content_type,
                filename=file.filename,
            )

        # --- Determine extension and save ---
        ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
        ext = ext_map.get(file.content_type, ".bin")
        filename = f"{uuid.uuid4().hex}{ext}"

        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = self.UPLOAD_DIR / filename
        dest.write_bytes(data)

        image_url = f"http://localhost:8000/api/v1/chat/uploads/{filename}"
        logger.info("upload.success", filename=filename, size=len(data))
        return {"image_url": image_url}

    async def serve_upload(self, filename: str):
        """Serve a previously uploaded image file."""
        filepath = self.UPLOAD_DIR / filename
        if not filepath.is_file():
            raise HTTPException(status_code=404, detail="File not found.")
        # Determine media type from extension
        media_types = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
        ext = filepath.suffix.lower()
        media_type = media_types.get(ext, "application/octet-stream")
        return FileResponse(str(filepath), media_type=media_type)


# Singleton controller instance
chat_controller = ChatController()
