"""LangGraph checkpointer — persists graph state in PostgreSQL."""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create_checkpointer() -> AsyncPostgresSaver:
    settings = get_settings()
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    checkpointer = AsyncPostgresSaver.from_conn_string(db_url)
    await checkpointer.setup()
    logger.info("checkpointer.initialized")
    return checkpointer
