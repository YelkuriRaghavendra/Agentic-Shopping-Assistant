from __future__ import annotations
import uuid
from typing import Any
from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    query:  str  = Field(..., min_length=1, max_length=2000)
    top_k:  int  = Field(default=5, ge=1, le=20)
    rerank: bool = True


class RetrievedChunk(BaseModel):
    chunk_id:    uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content:     str
    similarity:  float
    doc_type:    str
    product_id:  str | None
    metadata:    dict[str, Any]


class RetrievalResponse(BaseModel):
    query:       str
    results:     list[RetrievedChunk]
    total_found: int
    reranked:    bool
    latency_ms:  int
