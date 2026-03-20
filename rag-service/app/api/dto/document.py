from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    document_id: uuid.UUID
    source_id: uuid.UUID
    product_id: str | None
    document_type: str
    status: str
    token_count: int | None
    total_chunk_counts: int
    document_metadata: dict[str, Any]
    created_at: datetime
    last_updated_at: datetime | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, doc) -> "DocumentResponse":
        return cls(
            document_id=doc.document_id,
            source_id=doc.source_id,
            product_id=doc.product_id,
            document_type=doc.document_type,
            status=doc.status,
            token_count=doc.token_count,
            total_chunk_counts=doc.total_chunk_counts,
            document_metadata=doc.document_metadata,
            created_at=doc.created_at,
            last_updated_at=doc.last_updated_at,
        )


