"""
RAG Service client.

Single responsibility: talk to the RAG service.
Services never import httpx — they call this client.
"""

from dataclasses import dataclass
from app.clients.base_client import BaseHTTPClient
from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    product_id: str
    content:    str
    doc_type:   str
    metadata:   dict
    similarity: float


class RAGClient(BaseHTTPClient):

    def __init__(self):
        super().__init__(
            base_url=settings.RAG_SERVICE_URL,
            timeout=settings.RAG_TIMEOUT_SECONDS,
            headers={"X-API-Key": settings.RAG_API_KEY},
        )

    async def retrieve(
        self,
        query: str,
        filters: dict | None = None,
        top_k: int | None = None,
        request_id: str | None = None,
    ) -> list[RetrievedChunk]:
        """
        Semantic search against the RAG service.
        Returns empty list if service unavailable — chat still works,
        bot just says it couldn't find products.
        """
        try:
            payload = {
                "query":   query,
                "top_k":   top_k or settings.RAG_TOP_K,
                "filters": filters or {},
            }
            data = await self._post(
                "/api/v1/retrieve",
                payload=payload,
                request_id=request_id,
            )
            return [
                RetrievedChunk(
                    product_id=chunk.get("product_id", ""),
                    content=chunk.get("content", ""),
                    doc_type=chunk.get("doc_type", "product"),
                    metadata=chunk.get("metadata") or {},
                    similarity=chunk.get("similarity", 0.0),
                )
                for chunk in data.get("results", [])
            ]
        except Exception as e:
            # RAG failure is non-fatal — log and return empty
            logger.warning(
                "rag_client.retrieve_failed",
                query=query[:50],
                error=str(e),
            )
            return []

    async def health_check(self) -> bool:
        try:
            data = await self._get("/health")
            return data.get("status") == "ok"
        except Exception:
            return False
