from __future__ import annotations
import uuid
from typing import Any
from pydantic import BaseModel, Field


class RetrievalFilters(BaseModel):
    brand:     str | None = None
    category:  str | None = None
    document_type:  str | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)

    def to_metadata_filter(self) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        if self.brand:
            filters["brand"] = self.brand
        if self.category:
            filters["category"] = self.category
        return filters

class RetrievalRequest(BaseModel):
    query:   str  = Field(..., min_length=1, max_length=2000)
    top_k:   int  = Field(default=5, ge=1, le=20)
    rerank:  bool = True
    filters: RetrievalFilters | None = None


class RetrievedChunk(BaseModel):
    chunk_id:    uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content:     str
    similarity:  float
    document_type:    str
    product_id:  str | None
    metadata:    dict[str, Any]


class RetrievalResponse(BaseModel):
    query:       str
    results:     list[RetrievedChunk]
    total_found: int
    reranked:    bool
    latency_ms:  int
