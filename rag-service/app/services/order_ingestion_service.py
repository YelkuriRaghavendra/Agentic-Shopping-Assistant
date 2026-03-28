"""
Order ingestion service.

Consumes order.confirmed and order status-change events from checkout-order-service
and indexes them as user-scoped embeddings keyed by customer_id.

Design decisions:
- Each order is stored as a single Document with document_type=ORDER.
- The document's product_id field holds the order_id (reusing the column for
  the natural "external identifier" of the document).
- customer_id is stored in document_metadata so the retrieval layer can filter
  on it without a schema change.
- Re-indexing on status change: we delete the stale ORDER document for the
  order_id and re-ingest the updated content, triggering a fresh embed pipeline.
  This satisfies the ≤5-minute re-index SLA when called promptly after a change.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embedding_client import EmbeddingClient
from app.config.loader import INGESTION_CONFIG
from app.core.logging import get_logger
from app.db.models.chunk import Chunk
from app.db.models.document import Document
from app.db.models.embedding import Embedding
from app.db.models.enums.document_enums import DocumentStatus, DocumentType
from app.db.models.enums.job_enums import JobStatus
from app.db.models.jobs import Jobs
from app.db.repositories import (
    ChunkRepository,
    DocumentRepository,
    EmbeddingRepository,
    JobRepository,
    KnowledgeSourceRepository,
)
from app.services.chunking_service import chunk_text, count_tokens

logger = get_logger(__name__)

_embedding_client = EmbeddingClient()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _build_order_content(order: dict[str, Any]) -> str:
    """Render an order payload as plain text for embedding."""
    lines = [
        f"Order ID: {order.get('ucpOrderId') or order.get('order_id', '')}",
        f"Status: {order.get('status', 'processing')}",
        f"Customer ID: {order.get('customerId') or order.get('customer_id', '')}",
        f"Merchant ID: {order.get('merchantId') or order.get('merchant_id', '')}",
    ]

    totals = order.get("totals") or {}
    if totals:
        grand = totals.get("grand_total_cents", 0)
        lines.append(f"Grand Total: {grand} cents")

    line_items = order.get("lineItems") or order.get("line_items") or []
    if line_items:
        lines.append("Line Items:")
        for item_entry in line_items:
            item = item_entry.get("item", item_entry)
            qty = item_entry.get("quantity", 1)
            title = item.get("title", item.get("id", "unknown"))
            price = item.get("price", 0)
            lines.append(f"  - {title} x{qty} @ {price} cents")

    fulfillment = order.get("fulfillment") or {}
    events = fulfillment.get("events") or []
    if events:
        lines.append("Fulfillment Events:")
        for event in events:
            lines.append(f"  - {event.get('type', 'event')} at {event.get('occurred_at', '')}")

    permalink = order.get("ucpOrderPermalink") or order.get("permalink_url")
    if permalink:
        lines.append(f"Order Page: {permalink}")

    return "\n".join(lines)


def _build_order_metadata(order: dict[str, Any], customer_id: str) -> dict[str, Any]:
    """Build document metadata for customer-scoped retrieval filtering."""
    return {
        "customer_id": customer_id,
        "order_id": order.get("ucpOrderId") or order.get("order_id", ""),
        "status": order.get("status", "processing"),
        "merchant_id": order.get("merchantId") or order.get("merchant_id", ""),
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }


class OrderIngestionService:
    """
    Indexes order records as user-scoped embeddings.

    Usage:
        service = OrderIngestionService(db)
        await service.index_order(source_id, customer_id, order_payload)
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._document_repository = DocumentRepository(db)
        self._source_repository = KnowledgeSourceRepository(db)
        self._chunk_repository = ChunkRepository(db)
        self._embedding_repository = EmbeddingRepository(db)
        self._job_repository = JobRepository(db)

    async def index_order(
        self,
        source_id: Any,
        customer_id: str,
        order: dict[str, Any],
    ) -> tuple[Document, Jobs]:
        """
        Index (or re-index) an order document.

        - Deletes any existing ORDER document for this order_id first.
        - Creates a fresh document, chunks it, embeds it, and stores it.
        - Returns (document, job).
        """
        order_id = order.get("ucpOrderId") or order.get("order_id", "")
        if not order_id:
            raise ValueError("order payload must contain ucpOrderId or order_id")

        source = await self._source_repository.get_by_id(source_id)
        if not source:
            raise ValueError(f"Source {source_id} not found.")

        # Delete stale document for this order before re-indexing
        await self._delete_existing_order_doc(order_id)
        await self._db.flush()

        content = _build_order_content(order)
        metadata = _build_order_metadata(order, customer_id)
        content_hash = _sha256(content)

        document = Document(
            source_id=source_id,
            product_id=order_id,          # reuse product_id column as order_id
            document_type=DocumentType.ORDER,
            content=content,
            content_hash=content_hash,
            status=DocumentStatus.PENDING,
            token_count=count_tokens(content),
            document_metadata=metadata,
            created_by="system",
        )
        await self._document_repository.save(document)

        job = Jobs(
            document_id=document.document_id,
            status=JobStatus.QUEUED,
            started_at=datetime.now(timezone.utc),
            created_by="system",
        )
        await self._job_repository.save(job)
        await self._db.commit()

        logger.info(
            "order_ingestion.queued",
            order_id=order_id,
            customer_id=customer_id,
            document_id=str(document.document_id),
        )
        return document, job

    async def run_pipeline(self, document_id: Any) -> None:
        """Run the chunk→embed→store pipeline in a fresh session."""
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await OrderIngestionService(db)._pipeline(document_id)

    async def _pipeline(self, document_id: Any) -> None:
        document = await self._document_repository.get_by_id(document_id)
        job = await self._job_repository.get_by_document(document_id)
        if not document or not job:
            return

        try:
            await self._document_repository.set_status(document_id, DocumentStatus.PROCESSING)
            await self._job_repository.set_status_chunking(job.job_id)

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
                    chunk_index=c.chunk_index,
                    content=c.content,
                    token_count=c.token_count,
                    character_start=c.character_start,
                    character_end=c.character_end,
                    chunk_metadata={"customer_id": document.document_metadata.get("customer_id")},
                    created_by="system",
                )
                for c in chunks
            ]
            await self._chunk_repository.bulk_create(chunk_rows)
            await self._job_repository.set_status_embedding(job.job_id, len(chunk_rows))

            model = await self._embedding_repository.get_active_model()
            texts = [c.content for c in chunk_rows]
            vectors = await _embedding_client.embed_texts(texts, model.dimensions)

            embedding_rows = [
                Embedding(
                    chunk_id=chunk_rows[i].chunk_id,
                    llm_model_id=model.llm_model_id,
                    embedding=vectors[i],
                    created_by="system",
                )
                for i in range(len(chunk_rows))
            ]
            await self._embedding_repository.bulk_create(embedding_rows)
            await self._job_repository.update_progress(job.job_id, len(chunk_rows))

            await self._document_repository.set_status(document_id, DocumentStatus.READY)
            await self._job_repository.mark_done(job.job_id)
            await self._db.commit()

            logger.info(
                "order_ingestion.complete",
                document_id=str(document_id),
                chunks=len(chunk_rows),
            )

        except Exception as exc:
            await self._job_repository.mark_failed(job.job_id, str(exc))
            await self._document_repository.set_status(document_id, DocumentStatus.FAILED)
            await self._db.commit()
            logger.error("order_ingestion.failed", document_id=str(document_id), error=str(exc))
            raise

    async def _delete_existing_order_doc(self, order_id: str) -> None:
        """Remove any existing ORDER document for this order_id (for re-indexing)."""
        result = await self._db.execute(
            select(Document).where(
                Document.product_id == order_id,
                Document.document_type == DocumentType.ORDER,
            )
        )
        existing = result.scalars().all()
        for doc in existing:
            await self._db.delete(doc)
