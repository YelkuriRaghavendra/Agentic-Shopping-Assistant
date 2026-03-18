"""
Session repository.
All session-related DB operations live here.
Includes auto-session logic: find active or create new.
"""

import uuid
from datetime import datetime, timedelta, UTC
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.models import Session, SessionFeedback
from app.db.repositories.base_repository import BaseRepository
from app.core.config import get_settings

settings = get_settings()


class SessionRepository(BaseRepository[Session]):

    def __init__(self, db: AsyncSession):
        super().__init__(Session, db)

    async def find_active_for_customer(
        self,
        customer_id: uuid.UUID,
    ) -> Session | None:
        """
        Find the customer's current active session.
        Returns None if no active session or if the session has expired.
        """
        result = await self._db.execute(
            select(Session)
            .where(
                Session.customer_id == customer_id,
                Session.status == "active",
            )
            .order_by(Session.updated_at.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()
        if not session:
            return None

        # Check if session has gone idle past TTL
        ttl = timedelta(minutes=settings.SESSION_TTL_MINUTES)
        idle_since = datetime.now(UTC) - session.updated_at
        if idle_since > ttl:
            await self.expire(session.id)
            return None

        return session

    async def get_or_create(
        self,
        customer_id: uuid.UUID | None,
        channel: str = "web",
    ) -> tuple[Session, bool]:
        """
        Find active session for customer or create a new one.
        Returns (session, was_created).

        This is the core of auto-session:
        the caller just passes customer_id and gets a ready session.
        """
        if customer_id:
            existing = await self.find_active_for_customer(customer_id)
            if existing:
                return existing, False

        session = Session(
            customer_id=customer_id,
            channel=channel,
            status="active",
            context={},
            message_count=0,
            total_tokens=0,
        )
        await self.save(session)
        return session, True

    async def create(
        self,
        customer_id: uuid.UUID | None = None,
        channel: str = "web",
    ) -> Session:
        """Force-create a new session regardless of existing active sessions."""
        session = Session(
            customer_id=customer_id,
            channel=channel,
            status="active",
            context={},
        )
        return await self.save(session)

    async def increment_counters(
        self,
        session_id: uuid.UUID,
        turn_delta: int = 0,
        token_delta: int = 0,
    ) -> None:
        session = await self.get_by_id(session_id)
        if session:
            session.message_count += turn_delta
            session.total_tokens  += token_delta
            session.updated_at     = datetime.now(UTC)

    async def update_context(
        self,
        session: Session,
        context: dict,
    ) -> None:
        """
        Replace session context and mark JSONB as modified.
        Always call this instead of mutating session.context directly.
        """
        session.context    = context
        session.updated_at = datetime.now(UTC)
        self.mark_modified(session, "context")

    async def end(self, session_id: uuid.UUID) -> Session | None:
        session = await self.get_by_id(session_id)
        if session:
            session.status   = "ended"
            session.ended_at = datetime.now(UTC)
        return session

    async def expire(self, session_id: uuid.UUID) -> None:
        await self._db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(
                status="expired",
                ended_at=datetime.now(UTC),
            )
        )

    async def expire_idle_sessions(self) -> int:
        """
        Expire all sessions idle longer than SESSION_TTL_MINUTES.
        Called by a background job or on startup.
        Returns count of sessions expired.
        """
        cutoff = datetime.now(UTC) - timedelta(minutes=settings.SESSION_TTL_MINUTES)
        result = await self._db.execute(
            update(Session)
            .where(
                Session.status == "active",
                Session.updated_at < cutoff,
            )
            .values(status="expired", ended_at=datetime.now(UTC))
        )
        return result.rowcount

    async def add_feedback(
        self,
        session_id: uuid.UUID,
        rating: int,
        comment: str | None = None,
        feedback_type: str | None = None,
    ) -> SessionFeedback:
        feedback = SessionFeedback(
            session_id=session_id,
            rating=rating,
            comment=comment,
            feedback_type=feedback_type,
        )
        self._db.add(feedback)
        await self._db.flush()
        return feedback

    async def get_feedback(
        self,
        session_id: uuid.UUID,
    ) -> SessionFeedback | None:
        result = await self._db.execute(
            select(SessionFeedback).where(
                SessionFeedback.session_id == session_id
            )
        )
        return result.scalar_one_or_none()

    async def get_history(
        self,
        session_id: uuid.UUID,
        limit: int = 50,
        before_id: uuid.UUID | None = None,
    ) -> list:
        """Cursor-based pagination for message history."""
        from app.db.models.models import Message
        query = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        if before_id:
            # Get the created_at of the cursor message
            cursor_result = await self._db.execute(
                select(Message.created_at).where(Message.id == before_id)
            )
            cursor_ts = cursor_result.scalar_one_or_none()
            if cursor_ts:
                query = query.where(Message.created_at < cursor_ts)

        result = await self._db.execute(query)
        return list(reversed(result.scalars().all()))

    async def get_sessions_for_customer(
        self,
        customer_id: uuid.UUID,
        limit: int = 50,
    ) -> list[Session]:
        """Return all sessions for a customer, newest first."""
        result = await self._db.execute(
            select(Session)
            .where(Session.customer_id == customer_id)
            .order_by(Session.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

