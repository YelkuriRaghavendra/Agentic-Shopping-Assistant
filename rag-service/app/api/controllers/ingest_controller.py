"""
Ingest controller — HTTP boundary only.
Validates input, calls IngestionService, returns response.
No SQL, no business logic here.
"""
import asyncio
import uuid
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dto.ingest import (
    ProductIngestRequest, IngestResponse, JobsResponse,
    BulkProductIngestRequest, BulkIngestResponse,
)
from app.db.session import get_db
from app.db.repositories import JobRepository
from app.services.ingestion_service import IngestionService
from app.core.logging import get_logger
from app.db.models.enums.document_enums import DocumentType

logger = get_logger(__name__)


class IngestController:

    async def ingest_product(
        self,
        request: ProductIngestRequest,
        db: AsyncSession = Depends(get_db),
    ) -> IngestResponse:
        service = IngestionService(db)
        try:
            document, job, is_duplicate = await service.ingest(
                source_id=request.source_id,
                product_id=request.product_id,
                document_type=DocumentType.PRODUCT,
                content=request.to_content(),
                metadata=request.to_metadata(),
            )
        except ValueError as exception:
            raise HTTPException(status_code=400, detail=str(exception))
        if not is_duplicate:
            asyncio.create_task(service.run_pipeline(document.document_id))
        return IngestResponse(
            document_id=document.document_id,
            job_id=job.job_id if job else None,
            status="duplicate" if is_duplicate else "Queued",
            message="Duplicate." if is_duplicate else "Queued.",
        )

    async def ingest_products_bulk(
        self,
        request: BulkProductIngestRequest,
    ) -> BulkIngestResponse:
        total = len(request.products)
        logger.info("bulk_ingest.accepted", total=total)
        asyncio.create_task(self._process_bulk(request.products))
        return BulkIngestResponse(
            total=total,
            status="accepted",
            message=f"{total} products accepted for background processing.",
        )

    @staticmethod
    async def _process_bulk(products: list[ProductIngestRequest]) -> None:
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            service = IngestionService(db)
            for product in products:
                try:
                    document, job, is_duplicate = await service.ingest(
                        source_id=product.source_id,
                        product_id=product.product_id,
                        document_type=DocumentType.PRODUCT,
                        content=product.to_content(),
                        metadata=product.to_metadata(),
                    )
                    if not is_duplicate:
                        asyncio.create_task(service.run_pipeline(document.document_id))
                    logger.info(
                        "bulk_ingest.item_done",
                        product_id=product.product_id,
                        status="duplicate" if is_duplicate else "queued",
                    )
                except Exception as exc:
                    logger.error("bulk_ingest.item_failed", product_id=product.product_id, error=str(exc))

    async def get_job(
        self,
        job_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
    ) -> JobsResponse:
        repository = JobRepository(db)
        job = await repository.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        return JobsResponse.from_orm_model(job)


ingest_controller = IngestController()
