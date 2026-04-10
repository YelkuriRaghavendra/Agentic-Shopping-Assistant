"""
Persister node — saves messages and syncs state to database.
Runs after all processing is complete.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import MessageRepository, SessionRepository
from app.db.models.enums.message_enums import MessageRole, GuardrailStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_persister_node(db: AsyncSession, session_id: uuid.UUID):
    message_repo = MessageRepository(db)
    session_repo = SessionRepository(db)

    async def persister_node(state: dict) -> dict:
        messages = state.get("messages", [])
        if len(messages) < 1:
            return {}

        # Find last user message
        user_content = ""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                user_content = msg.content
                break

        agent_response = state.get("agent_response", "")
        intent = state.get("intent", "")
        guardrail_status_str = state.get("guardrail_status", "passed")
        guard_status = GuardrailStatus.PASSED if guardrail_status_str == "passed" else GuardrailStatus.WARNED
        cited_products = state.get("cited_products", [])

        if user_content:
            await message_repo.create(
                session_id=session_id, role=MessageRole.USER,
                content=user_content, intent=intent, guardrail_status=GuardrailStatus.PASSED,
            )

        bot_msg = None
        if agent_response:
            bot_msg = await message_repo.create(
                session_id=session_id, role=MessageRole.ASSISTANT,
                content=agent_response, intent=intent,
                guardrail_status=guard_status, cited_products=cited_products,
            )

        est_tokens = len(agent_response) // 4
        await session_repo.increment_counters(session_id=session_id, turn_delta=2, token_delta=est_tokens)
        await db.commit()

        return {"message_id": str(bot_msg.message_id)} if bot_msg else {}

    return persister_node
