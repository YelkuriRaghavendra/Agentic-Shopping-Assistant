from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class KnowledgeSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source_type: Literal[
        "manual", "file_upload", "csv", "pdf",
        "shopify", "api_push", "bulk_jsonl"
    ]
    config: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSourceResponse(BaseModel):
    source_id: uuid.UUID
    source_name: str
    source_type: str
    source_config: dict[str, Any]
    status: str
    last_synced_at: datetime | None
    created_at: datetime
    last_updated_at: datetime | None

    model_config = {"from_attributes": True}
