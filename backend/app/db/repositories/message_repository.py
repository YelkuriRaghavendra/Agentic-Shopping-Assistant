"""
Message repository.
All message and feedback DB operations live here.
"""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.models import Message, MessageFeedback
from app.db.repositories.base_repository import BaseRepository


class MessageRepository(BaseRepository[Message]):

    def __init__(self, db: AsyncSession):
        super().__init__(Message, db)

    async def create(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        **kwargs,
    ) -> Message:
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            **kwargs,
        )
        return await self.save(message)

    async def get_recent_turns(
        self,
        session_id: uuid.UUID,
        limit: int = 12,  # 6 turns = 12 messages (user + assistant each)
    ) -> list[Message]:
        """
        Returns the most recent N messages in chronological order.
        Used to build the LLM conversation history window.
        """
        result = await self._db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def get_page(
        self,
        session_id: uuid.UUID,
        limit: int = 50,
        before_id: uuid.UUID | None = None,
    ) -> list[Message]:
        """
        Cursor-based pagination — returns messages before the cursor.
        Use returned[-1].id as the next cursor.
        """
        query = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        if before_id:
            cursor_result = await self._db.execute(
                select(Message.created_at).where(Message.id == before_id)
            )
            cursor_ts = cursor_result.scalar_one_or_none()
            if cursor_ts:
                query = query.where(Message.created_at < cursor_ts)

        result = await self._db.execute(query)
        # Reverse so messages are in chronological order
        return list(reversed(result.scalars().all()))

    async def add_feedback(
        self,
        message_id: uuid.UUID,
        rating: int,
        comment: str | None = None,
        feedback_type: str | None = None,
    ) -> MessageFeedback:
        feedback = MessageFeedback(
            message_id=message_id,
            rating=rating,
            comment=comment,
            feedback_type=feedback_type,
        )
        self._db.add(feedback)
        await self._db.flush()
        return feedback

    async def get_feedback(
        self,
        message_id: uuid.UUID,
    ) -> MessageFeedback | None:
        result = await self._db.execute(
            select(MessageFeedback).where(
                MessageFeedback.message_id == message_id
            )
        )
        return result.scalar_one_or_none()
