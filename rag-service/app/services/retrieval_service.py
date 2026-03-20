"""
Retrieval service.

Embeds the query, searches pgvector for nearest chunks,
optionally reranks with a cross-encoder, returns top results.

Configuration from config/retrieval_config.json.
All SQL via raw text queries. All API calls via clients.
"""

import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.cross_encoder_client import CrossEncoderClient
from app.clients.embedding_client import EmbeddingClient
from app.config.loader import RETRIEVAL_CONFIG
from app.core.logging import get_logger
from app.db.repositories.chunk_repository import EmbeddingRepository

logger = get_logger(__name__)

_embedding_client = EmbeddingClient()
_cross_encoder_client: CrossEncoderClient | None = None


def _get_cross_encoder(model_name: str) -> CrossEncoderClient:
    global _cross_encoder_client
    if _cross_encoder_client is None:
        _cross_encoder_client = CrossEncoderClient(model_name)
    return _cross_encoder_client


@dataclass
class RetrievedResult:
    chunk_id:    UUID | None
    document_id: UUID | None
    chunk_index: int
    content:     str
    similarity:  float
    doc_type:    str
    product_id:  str | None
    metadata:    dict[str, Any]


class RetrievalService:

    def __init__(self, db: AsyncSession):
        self._db                   = db
        self._embedding_repository = EmbeddingRepository(db)

    async def retrieve(
        self,
        query:  str,
        top_k:  int  = 5,
        rerank: bool = True,
    ) -> list[RetrievedResult]:
        start_time = time.monotonic()

        candidates = await self._vector_search(query, top_k, rerank)

        latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.info("retrieval.complete", results=len(candidates), latency_ms=latency_ms)
        return candidates

    async def _vector_search(
        self,
        query:  str,
        top_k:  int,
        rerank: bool,
    ) -> list[RetrievedResult]:
        vs_config    = RETRIEVAL_CONFIG["vector_search"]
        rerank_cfg   = RETRIEVAL_CONFIG["reranking"]
        min_score    = vs_config["min_score"]
        ef_search    = vs_config["hnsw_ef_search"]
        # fetch more candidates when reranking, else fetch exactly top_k
        fetch_count  = rerank_cfg["max_candidates"] if rerank and rerank_cfg["enabled"] else top_k

        active_model = await self._embedding_repository.get_active_model()
        query_vector = await _embedding_client.embed_single(query, active_model.dimensions)

        # tune HNSW recall for this query
        await self._db.execute(text(f"SET LOCAL hnsw.ef_search = {ef_search}"))

        sql = text("""
            SELECT
                c.chunk_id,
                c.document_id,
                c.chunk_index,
                c.content,
                c.metadata      AS chunk_metadata,
                d.product_id,
                d.document_type AS doc_type,
                d.metadata      AS doc_metadata,
                1 - (e.embedding <=> CAST(:query_vector AS vector)) AS similarity
            FROM embeddings e
            JOIN chunks     c ON c.chunk_id     = e.chunk_id
            JOIN documents  d ON d.document_id  = c.document_id
            JOIN llm_models m ON m.llm_model_id = e.llm_model_id
            WHERE m.is_active        = TRUE
              AND d.status           = 'READY'
              AND d.document_type    = 'PRODUCT'
              AND (1 - (e.embedding <=> CAST(:query_vector AS vector))) >= :min_score
            ORDER BY e.embedding <=> CAST(:query_vector AS vector)
            LIMIT :fetch_count
        """)

        rows = (await self._db.execute(sql, {
            "query_vector": str(query_vector),
            "min_score":    min_score,
            "fetch_count":  fetch_count,
        })).mappings().all()

        candidates = [
            RetrievedResult(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                similarity=round(float(row["similarity"]), 4),
                doc_type=row["doc_type"],
                product_id=row["product_id"],
                metadata={**(row["doc_metadata"] or {}), **(row["chunk_metadata"] or {})},
            )
            for row in rows
        ]

        if not candidates:
            return []

        if rerank and len(candidates) > top_k:
            return await self._rerank(query, candidates, top_k)

        return candidates[:top_k]

    async def _rerank(
        self,
        query:      str,
        candidates: list[RetrievedResult],
        top_k:      int,
    ) -> list[RetrievedResult]:
        rerank_config = RETRIEVAL_CONFIG["reranking"]
        if not rerank_config["enabled"] or len(candidates) <= top_k:
            return candidates[:top_k]
        try:
            pairs  = [(query, result.content) for result in candidates]
            scores = await _get_cross_encoder(rerank_config["model"]).score(pairs)
            ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
            return [result for _, result in ranked[:top_k]]
        except Exception as exc:
            logger.warning("rerank.failed", error=str(exc))
            return candidates[:top_k]
