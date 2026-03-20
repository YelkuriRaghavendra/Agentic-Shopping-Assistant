"""
Ingestion service.

Orchestrates the full ingestion pipeline:
  raw content → deduplication → save document → chunk → embed → store → done

Uses repositories for all DB operations.
Uses EmbeddingClient for all embedding calls.
All configuration comes from config/ingestion_config.json.
"""

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embedding_client import EmbeddingClient
from app.config.loader import INGESTION_CONFIG
from app.core.logging import get_logger
from app.db.models.chunk import Chunk
from app.db.models.document import Document
from app.db.models.embedding import Embedding
from app.db.models.jobs import Jobs
from app.db.repositories import (
    DocumentRepository, KnowledgeSourceRepository,
    ChunkRepository, EmbeddingRepository, JobRepository,
)
from app.services.chunking_service import chunk_text, count_tokens
from app.db.models.enums.document_enums import DocumentStatus, DocumentType
from app.db.models.enums.job_enums import JobStatus


logger = get_logger(__name__)

_embedding_client = EmbeddingClient()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class IngestionService:
    """
    All ingestion logic lives here.
    No SQL, no HTTP — delegates to repositories and clients.
    """

    def __init__(self, db: AsyncSession):
        self._db                   = db
        self._document_repository  = DocumentRepository(db)
        self._source_repository    = KnowledgeSourceRepository(db)
        self._chunk_repository     = ChunkRepository(db)
        self._embedding_repository = EmbeddingRepository(db)
        self._job_repository       = JobRepository(db)

    async def ingest(
        self,
        source_id: UUID,
        product_id: str | None,
        document_type: str,
        content: str,
        metadata: dict,
    ) -> tuple[Document, Jobs, bool]:
        """
        Ingest a document.
        Returns (document, job, was_duplicate).
        Raises ValueError if source not found.
        The pipeline runs in background — caller polls the job for progress.
        """
        config = INGESTION_CONFIG

        # Verify source exists
        source = await self._source_repository.get_by_id(source_id)
        if not source:
            raise ValueError(f"Source {source_id} not found.")

        content_hash = _sha256(content)

        # Exact-content dedup — same product, same content, already indexed
        if config["deduplication"]["enabled"]:
            existing = await self._document_repository.find_by_hash(content_hash)
            if existing:
                job = await self._job_repository.get_by_document(existing.document_id)
                return existing, job, True

        # Product re-ingestion — delete stale docs for this product_id before inserting
        if product_id and document_type == DocumentType.PRODUCT:
            await self._document_repository.delete_by_product_id(product_id)
            await self._db.flush()

        # Create document row
        document = Document(
            source_id=source_id,
            product_id=product_id,
            document_type=document_type,
            content=content,
            content_hash=content_hash,
            status=DocumentStatus.PENDING,
            token_count=count_tokens(content),
            document_metadata=metadata,
            created_by="system",
        )
        await self._document_repository.save(document)

        # Create job row
        job = Jobs(
            document_id=document.document_id,
            status=JobStatus.QUEUED,
            started_at=datetime.now(timezone.utc),
            created_by="system",
        )
        await self._job_repository.save(job)
        await self._db.commit()

        return document, job, False

    async def run_pipeline(self, document_id: UUID) -> None:
        """
        Run the full chunk→embed→store pipeline.
        Called as a background task after ingest().
        Creates its own DB session via AsyncSessionLocal.
        """
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            service = IngestionService(db)
            await service._pipeline(document_id)

    async def _pipeline(self, document_id: UUID) -> None:
        """Internal pipeline — runs inside its own session."""
        document = await self._document_repository.get_by_id(document_id)
        job      = await self._job_repository.get_by_document(document_id)
        if not document or not job:
            return

        try:
            await self._document_repository.set_status(document_id, DocumentStatus.PROCESSING)
            await self._job_repository.set_status_chunking(job.job_id)

            # 1. Chunk
            config = INGESTION_CONFIG["chunking"]
            chunks = chunk_text(
                document.content or "",
                chunk_size=config["default_chunk_size_tokens"],
                overlap=config["default_overlap_tokens"],
                min_chunk=config["min_chunk_size_tokens"],
            )
            chunk_rows = [
                Chunk(
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    character_start=chunk.character_start,
                    character_end=chunk.character_end,
                    chunk_metadata={},
                    created_by="system",
                )
                for chunk in chunks
            ]
            await self._chunk_repository.bulk_create(chunk_rows)
            await self._job_repository.set_status_embedding(job.job_id, len(chunk_rows))

            # 2. Embed
            model   = await self._embedding_repository.get_active_model()
            texts   = [chunk.content for chunk in chunk_rows]
            vectors = await _embedding_client.embed_texts(texts, model.dimensions)

            embedding_rows = [
                Embedding(
                    chunk_id=chunk_rows[index].chunk_id,
                    llm_model_id=model.llm_model_id,
                    embedding=vectors[index],
                    created_by="system",
                )
                for index in range(len(chunk_rows))
            ]
            await self._embedding_repository.bulk_create(embedding_rows)
            await self._job_repository.update_progress(job.job_id, len(chunk_rows))

            # 3. Mark ready
            await self._document_repository.set_status(document_id, DocumentStatus.READY)
            await self._db.execute(
                update(Document)
                .where(Document.document_id == document_id)
                .values(total_chunk_counts=len(chunk_rows))
            )
            await self._job_repository.mark_done(job.job_id)
            await self._db.commit()

            logger.info(
                "ingestion.complete",
                document_id=str(document_id),
                chunks=len(chunk_rows),
            )

        except Exception as exception:
            await self._job_repository.mark_failed(job.job_id, str(exception))
            await self._document_repository.set_status(document_id, DocumentStatus.FAILED)
            await self._db.commit()
            logger.error("ingestion.failed", document_id=str(document_id), error=str(exception))
            raise
