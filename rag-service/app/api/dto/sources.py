from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator

from app.db.models.enums.source_enums import SourceType


class KnowledgeSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source_type: SourceType
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_type", mode="before")
    @classmethod
    def normalise_source_type(cls, v: str) -> str:
        if isinstance(v, str):
            return v.upper()
        return v


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
