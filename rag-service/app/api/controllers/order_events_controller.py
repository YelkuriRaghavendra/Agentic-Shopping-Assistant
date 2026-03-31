"""
Order events controller — HTTP boundary only.

Receives order.confirmed and order status-change events from checkout-order-service
and triggers order embedding (re-)indexing via OrderIngestionService.
"""
import asyncio
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dto.order_events import OrderEventRequest, OrderIndexResponse
from app.db.session import get_db
from app.services.order_ingestion_service import OrderIngestionService
from app.core.logging import get_logger

logger = get_logger(__name__)


class OrderEventsController:

    async def index_order(
        self,
        request: OrderEventRequest,
        db: AsyncSession = Depends(get_db),
    ) -> OrderIndexResponse:
        service = OrderIngestionService(db)
        try:
            document, job = await service.index_order(
                source_id=request.source_id,
                customer_id=request.customer_id,
                order=request.order,
            )
        except ValueError as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=str(exc))

        # Run the embed pipeline as a background task
        asyncio.create_task(service.run_pipeline(document.document_id))

        return OrderIndexResponse(
            document_id=document.document_id,
            job_id=job.job_id if job else None,
            status="queued",
            message="Order queued for embedding.",
        )


order_events_controller = OrderEventsController()
