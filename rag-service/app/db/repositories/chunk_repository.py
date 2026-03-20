"""Chunk + Embedding + Jobs repository."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.chunk import Chunk
from app.db.models.embedding import Embedding, LLMModel
from app.db.models.jobs import Jobs
from app.db.models.enums.job_enums import JobStatus
from app.db.repositories.base_repository import BaseRepository


class ChunkRepository(BaseRepository[Chunk]):
    def __init__(self, db: AsyncSession):
        super().__init__(Chunk, db, "chunk_id")


class EmbeddingRepository(BaseRepository[Embedding]):
    def __init__(self, db: AsyncSession):
        super().__init__(Embedding, db, "embedding_id")

    async def get_active_model(self) -> LLMModel:
        result = await self._db.execute(
            select(LLMModel).where(LLMModel.is_active.is_(True)).limit(1)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise RuntimeError("No active embedding model. Run seed migration.")
        return model


class JobRepository(BaseRepository[Jobs]):
    def __init__(self, db: AsyncSession):
        super().__init__(Jobs, db, "job_id")

    async def get_by_document(self, document_id: uuid.UUID) -> Jobs | None:
        result = await self._db.execute(
            select(Jobs).where(Jobs.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def _update(self, job_id: uuid.UUID, **values) -> None:
        await self._db.execute(
            update(Jobs).where(Jobs.job_id == job_id).values(**values)
        )

    async def set_status_chunking(self, job_id: uuid.UUID) -> None:
        await self._update(job_id, status=JobStatus.CHUNKING)
        await self._db.flush()

    async def set_status_embedding(self, job_id: uuid.UUID, chunks_total: int) -> None:
        await self._update(job_id, status=JobStatus.EMBEDDING, chunks_total=chunks_total)
        await self._db.flush()

    async def update_progress(self, job_id: uuid.UUID, chunks_done: int) -> None:
        await self._update(job_id, chunks_done=chunks_done)

    async def mark_done(self, job_id: uuid.UUID) -> None:
        await self._update(job_id, status=JobStatus.DONE, finished_at=datetime.now(timezone.utc))

    async def mark_failed(self, job_id: uuid.UUID, error: str) -> None:
        await self._update(job_id, status=JobStatus.FAILED, error_message=error[:2000], finished_at=datetime.now(timezone.utc))
