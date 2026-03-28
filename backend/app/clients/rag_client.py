"""
RAG Service client.

Single responsibility: talk to the RAG service.
Services never import httpx — they call this client.
"""

from dataclasses import dataclass, asdict
from app.clients.base_client import BaseHTTPClient
from app.clients.redis_client import cache_get, cache_set, make_cache_key
from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    product_id: str
    content:    str
    document_type:   str
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
        Results are cached in Redis for CACHE_RAG_TTL seconds.
        Returns empty list if service unavailable — chat still works,
        bot just says it couldn't find products.
        """
        effective_filters = filters or {}
        effective_top_k = top_k or settings.RAG_TOP_K

        # ── Check cache ──────────────────────────────────────────────
        cache_key = f"rag:{make_cache_key(query, str(effective_filters), str(effective_top_k))}"
        cached = await cache_get(cache_key)
        if cached is not None:
            logger.debug("rag_client.cache_hit", query=query[:50])
            return [RetrievedChunk(**c) for c in cached]

        # ── Call RAG service ─────────────────────────────────────────
        try:
            payload = {
                "query":   query,
                "top_k":   effective_top_k,
                "filters": effective_filters,
            }
            data = await self._post(
                "/api/v1/retrieve",
                payload=payload,
                request_id=request_id,
            )
            chunks = [
                RetrievedChunk(
                    product_id=chunk.get("product_id", ""),
                    content=chunk.get("content", ""),
                    document_type=chunk.get("document_type", "product"),
                    metadata=chunk.get("metadata") or {},
                    similarity=chunk.get("similarity", 0.0),
                )
                for chunk in data.get("results", [])
            ]

            # ── Cache result ─────────────────────────────────────────
            if chunks:
                await cache_set(
                    cache_key,
                    [asdict(c) for c in chunks],
                    ttl=settings.CACHE_RAG_TTL,
                )

            return chunks
        except Exception as e:
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
