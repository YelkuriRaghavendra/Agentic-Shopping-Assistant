"""
Retrieve controller — HTTP boundary only.
"""
import time
import uuid
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dto.retrieve import RetrievalRequest, RetrievalResponse, RetrievedChunk
from app.db.session import get_db
from app.services.retrieval_service import RetrievalService
from app.core.logging import get_logger

logger = get_logger(__name__)


class RetrieveController:

    async def retrieve(
        self,
        request: RetrievalRequest,
        db: AsyncSession = Depends(get_db),
    ) -> RetrievalResponse:
        time_start = time.monotonic()
        service    = RetrievalService(db)

        filters = request.filters.to_metadata_filter() if request.filters else {}
        if request.filters and request.filters.max_price is not None:
            filters["max_price"] = request.filters.max_price
        if request.filters and request.filters.min_price is not None:
            filters["min_price"] = request.filters.min_price
        results = await service.retrieve(
            query=request.query,
            top_k=request.top_k,
            filters=filters,
            rerank=request.rerank,
            doc_type=request.filters.document_type if request.filters else None,
        )

        chunks = [
            RetrievedChunk(
                chunk_id=retrieved_result.chunk_id or uuid.uuid4(),
                document_id=retrieved_result.document_id or uuid.uuid4(),
                chunk_index=retrieved_result.chunk_index,
                content=retrieved_result.content,
                similarity=retrieved_result.similarity,
                document_type=retrieved_result.doc_type,
                product_id=retrieved_result.product_id,
                metadata=retrieved_result.metadata,
            )
            for retrieved_result in results
        ]
        return RetrievalResponse(
            query=request.query,
            results=chunks,
            total_found=len(chunks),
            reranked=request.rerank and len(results) > 0,
            latency_ms=int((time.monotonic() - time_start) * 1000),
        )


retrieve_controller = RetrieveController()
