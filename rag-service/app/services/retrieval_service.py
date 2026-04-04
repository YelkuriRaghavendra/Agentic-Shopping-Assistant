"""
Retrieval service.

Embeds the query, searches pgvector for nearest chunks,
optionally reranks with a cross-encoder, returns top results.

Configuration from config/retrieval_config.json.
All SQL via raw text queries. All API calls via clients.
"""

import re
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
from app.db.models.enums.document_enums import DocumentType
from app.db.repositories.chunk_repository import EmbeddingRepository

_VALID_DOC_TYPES = {dt.value for dt in DocumentType}

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "and", "but", "or", "if", "while", "because", "until", "about",
    "this", "that", "these", "those", "i", "me", "my", "we", "our",
    "you", "your", "he", "him", "his", "she", "her", "it", "its",
    "they", "them", "their", "what", "which", "who", "whom",
    "show", "find", "get", "give", "tell", "want", "looking",
})

_RRF_K = 60  # Reciprocal Rank Fusion constant

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
        filters: dict[str, Any] | None = None,
        doc_type: str | None = None,
        hybrid: bool = True,
    ) -> list[RetrievedResult]:
        start_time = time.monotonic()

        vector_results = await self._vector_search(
            query, top_k, rerank, filters=filters, doc_type=doc_type,
        )

        if hybrid:
            keywords = self._extract_keywords(query)
            if keywords:
                keyword_results = await self._keyword_search(
                    keywords, top_k, filters=filters, doc_type=doc_type,
                )
                if keyword_results:
                    candidates = self._rrf_merge(vector_results, keyword_results, top_k)
                    latency_ms = int((time.monotonic() - start_time) * 1000)
                    logger.info(
                        "retrieval.hybrid_complete",
                        mode="dense+bm25+reranker" if rerank else "dense+bm25",
                        vector_hits=len(vector_results),
                        bm25_hits=len(keyword_results),
                        rrf_merged=len(candidates),
                        latency_ms=latency_ms,
                    )
                    return candidates

        latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.info("retrieval.complete", results=len(vector_results), latency_ms=latency_ms)
        return vector_results

    async def _vector_search(
        self,
        query:  str,
        top_k:  int,
        rerank: bool,
        filters: dict[str, Any] | None = None,
        doc_type: str | None = None,
    ) -> list[RetrievedResult]:
        vs_config    = RETRIEVAL_CONFIG["vector_search"]
        rerank_cfg   = RETRIEVAL_CONFIG["reranking"]
        min_score    = vs_config["min_score"]
        ef_search    = int(vs_config["hnsw_ef_search"])  # ensure it's an integer
        # fetch more candidates when reranking, else fetch exactly top_k
        fetch_count  = rerank_cfg["max_candidates"] if rerank and rerank_cfg["enabled"] else top_k

        active_model = await self._embedding_repository.get_active_model()
        query_vector = await _embedding_client.embed_single(query, active_model.dimensions)

        # tune HNSW recall for this query
        # SET LOCAL doesn't support bind params in asyncpg; int() cast prevents injection
        ef_search = int(ef_search)
        await self._db.execute(text(f"SET LOCAL hnsw.ef_search = {ef_search}"))

        # Build dynamic WHERE clauses based on filters
        where_clauses = [
            "m.is_active = TRUE",
            "d.status = 'READY'",
            "(1 - (e.embedding <=> CAST(:query_vector AS vector))) >= :min_score",
        ]
        params: dict[str, Any] = {
            "query_vector": str(query_vector),
            "min_score":    min_score,
            "fetch_count":  fetch_count,
        }

        # doc_type filter (defaults to PRODUCT) — validate against known enum values
        resolved_doc_type = (doc_type or "PRODUCT").upper()
        if resolved_doc_type not in _VALID_DOC_TYPES:
            logger.warning("retrieval.invalid_doc_type", provided=resolved_doc_type, fallback="PRODUCT")
            resolved_doc_type = "PRODUCT"
        where_clauses.append("d.document_type = :doc_type")
        params["doc_type"] = resolved_doc_type

        # metadata filters
        if filters:
            if filters.get("brand"):
                where_clauses.append("d.metadata->>'brand' ILIKE :brand")
                params["brand"] = filters["brand"]
            if filters.get("category"):
                where_clauses.append("d.metadata->>'category' ILIKE :category")
                params["category"] = filters["category"]
            if filters.get("max_price") is not None and filters["max_price"] > 0:
                where_clauses.append("CAST(d.metadata->>'price' AS FLOAT) <= :max_price")
                params["max_price"] = filters["max_price"]
            if filters.get("min_price") is not None and filters["min_price"] > 0:
                where_clauses.append("CAST(d.metadata->>'price' AS FLOAT) >= :min_price")
                params["min_price"] = filters["min_price"]
            if filters.get("in_stock") is not None:
                where_clauses.append("(d.metadata->>'in_stock')::boolean = :in_stock")
                params["in_stock"] = filters["in_stock"]
            if filters.get("color"):
                where_clauses.append("d.metadata->>'color' ILIKE :color")
                params["color"] = filters["color"]

        # Requirement 12.2, 12.4 — ORDER embeddings MUST be scoped to a customer_id.
        # If doc_type is ORDER and no customer_id filter is provided, return nothing
        # to prevent cross-customer data leakage.
        if resolved_doc_type == "ORDER":
            customer_id = (filters or {}).get("customer_id")
            if not customer_id:
                logger.warning(
                    "retrieval.order_query_missing_customer_id",
                    msg="ORDER retrieval requires customer_id filter; returning empty results",
                )
                return []
            where_clauses.append("d.metadata->>'customer_id' = :customer_id")
            params["customer_id"] = customer_id

        where_sql = " AND ".join(where_clauses)

        sql = text(f"""
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
            WHERE {where_sql}
            ORDER BY e.embedding <=> CAST(:query_vector AS vector)
            LIMIT :fetch_count
        """)

        rows = (await self._db.execute(sql, params)).mappings().all()

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

    @staticmethod
    def _extract_keywords(query: str) -> list[str]:
        """Split query into words, strip non-alpha chars, drop stop words."""
        words = re.findall(r"[a-zA-Z0-9]+", query.lower())
        return [w for w in words if w not in _STOP_WORDS and len(w) > 1]

    async def _keyword_search(
        self,
        keywords: list[str],
        top_k: int,
        filters: dict[str, Any] | None = None,
        doc_type: str | None = None,
    ) -> list[RetrievedResult]:
        """
        BM25-like keyword search using PostgreSQL full-text search (ts_vector + ts_rank).

        Falls back to ILIKE if ts_vector is unavailable. ts_rank uses a normalization
        that divides by document length (flag 1), which approximates BM25's length norm.
        """
        resolved_doc_type = (doc_type or "PRODUCT").upper()
        if resolved_doc_type not in _VALID_DOC_TYPES:
            resolved_doc_type = "PRODUCT"

        where_clauses = [
            "d.status = 'READY'",
            "d.document_type = :doc_type",
        ]
        params: dict[str, Any] = {
            "doc_type": resolved_doc_type,
            "fetch_count": top_k * 3,
        }

        # Build ts_query from keywords: word1 & word2 & word3 (AND logic)
        ts_query_str = " & ".join(keywords)
        params["ts_query"] = ts_query_str

        # Full-text search condition using to_tsvector/to_tsquery
        where_clauses.append(
            "to_tsvector('english', c.content) @@ to_tsquery('english', :ts_query)"
        )

        # Apply the same metadata filters as vector search
        if filters:
            if filters.get("brand"):
                where_clauses.append("d.metadata->>'brand' ILIKE :brand")
                params["brand"] = filters["brand"]
            if filters.get("category"):
                where_clauses.append("d.metadata->>'category' ILIKE :category")
                params["category"] = filters["category"]
            if filters.get("max_price") is not None and filters["max_price"] > 0:
                where_clauses.append("CAST(d.metadata->>'price' AS FLOAT) <= :max_price")
                params["max_price"] = filters["max_price"]
            if filters.get("min_price") is not None and filters["min_price"] > 0:
                where_clauses.append("CAST(d.metadata->>'price' AS FLOAT) >= :min_price")
                params["min_price"] = filters["min_price"]
            if filters.get("in_stock") is not None:
                where_clauses.append("(d.metadata->>'in_stock')::boolean = :in_stock")
                params["in_stock"] = filters["in_stock"]
            if filters.get("color"):
                where_clauses.append("d.metadata->>'color' ILIKE :color")
                params["color"] = filters["color"]

        # ORDER doc_type requires customer_id scoping
        if resolved_doc_type == "ORDER":
            customer_id = (filters or {}).get("customer_id")
            if not customer_id:
                return []
            where_clauses.append("d.metadata->>'customer_id' = :customer_id")
            params["customer_id"] = customer_id

        where_sql = " AND ".join(where_clauses)

        # ts_rank with normalization flag 1 (divides by document length) ≈ BM25 length norm
        sql = text(f"""
            SELECT
                c.chunk_id,
                c.document_id,
                c.chunk_index,
                c.content,
                c.metadata      AS chunk_metadata,
                d.product_id,
                d.document_type AS doc_type,
                d.metadata      AS doc_metadata,
                ts_rank(
                    to_tsvector('english', c.content),
                    to_tsquery('english', :ts_query),
                    1
                ) AS bm25_score
            FROM chunks    c
            JOIN documents d ON d.document_id = c.document_id
            WHERE {where_sql}
            ORDER BY bm25_score DESC
            LIMIT :fetch_count
        """)

        try:
            rows = (await self._db.execute(sql, params)).mappings().all()
        except Exception as exc:
            # Fall back to simple ILIKE if full-text search fails
            logger.warning("bm25_search.falling_back_to_ilike", error=str(exc))
            return await self._ilike_fallback(keywords, top_k, filters, resolved_doc_type)

        return [
            RetrievedResult(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                similarity=float(row["bm25_score"]),
                doc_type=row["doc_type"],
                product_id=row["product_id"],
                metadata={**(row["doc_metadata"] or {}), **(row["chunk_metadata"] or {})},
            )
            for row in rows
        ]

    async def _ilike_fallback(
        self,
        keywords: list[str],
        top_k: int,
        filters: dict[str, Any] | None,
        resolved_doc_type: str,
    ) -> list[RetrievedResult]:
        """Simple ILIKE fallback when ts_vector is unavailable."""
        where_clauses = ["d.status = 'READY'", "d.document_type = :doc_type"]
        params: dict[str, Any] = {"doc_type": resolved_doc_type, "fetch_count": top_k * 2}

        for idx, kw in enumerate(keywords):
            pn = f"kw_{idx}"
            where_clauses.append(f"c.content ILIKE :{pn}")
            params[pn] = f"%{kw}%"

        if filters:
            if filters.get("brand"):
                where_clauses.append("d.metadata->>'brand' ILIKE :brand")
                params["brand"] = filters["brand"]
            if filters.get("color"):
                where_clauses.append("d.metadata->>'color' ILIKE :color")
                params["color"] = filters["color"]

        where_sql = " AND ".join(where_clauses)
        sql = text(f"""
            SELECT c.chunk_id, c.document_id, c.chunk_index, c.content,
                   c.metadata AS chunk_metadata, d.product_id,
                   d.document_type AS doc_type, d.metadata AS doc_metadata
            FROM chunks c JOIN documents d ON d.document_id = c.document_id
            WHERE {where_sql} LIMIT :fetch_count
        """)
        try:
            rows = (await self._db.execute(sql, params)).mappings().all()
        except Exception as exc:
            logger.warning("ilike_fallback.failed", error=str(exc))
            return []

        return [
            RetrievedResult(
                chunk_id=row["chunk_id"], document_id=row["document_id"],
                chunk_index=row["chunk_index"], content=row["content"],
                similarity=0.0, doc_type=row["doc_type"],
                product_id=row["product_id"],
                metadata={**(row["doc_metadata"] or {}), **(row["chunk_metadata"] or {})},
            )
            for row in rows
        ]

    @staticmethod
    def _rrf_merge(
        vector_results: list[RetrievedResult],
        keyword_results: list[RetrievedResult],
        top_k: int,
    ) -> list[RetrievedResult]:
        """Merge two ranked lists using Reciprocal Rank Fusion (RRF)."""
        scores: dict[UUID | None, float] = {}
        result_map: dict[UUID | None, RetrievedResult] = {}

        for rank, r in enumerate(vector_results):
            scores[r.chunk_id] = scores.get(r.chunk_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
            result_map[r.chunk_id] = r

        for rank, r in enumerate(keyword_results):
            scores[r.chunk_id] = scores.get(r.chunk_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
            # Prefer the vector result entry (has similarity score) if already present
            if r.chunk_id not in result_map:
                result_map[r.chunk_id] = r

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [result_map[chunk_id] for chunk_id, _ in ranked[:top_k]]
