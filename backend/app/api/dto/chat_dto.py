"""
Chat DTOs — Data Transfer Objects.

These define the public API contract:
  - What the client sends (Request DTOs)
  - What the client receives (Response DTOs)

Rules:
  - No SQLAlchemy imports
  - No business logic
  - Pure Pydantic models
  - Versioned: if the API shape changes, create v2 DTOs
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Inbound DTOs
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """
    Main chat endpoint.

    session_id is OPTIONAL.
    If provided, continues that session.
    If omitted, the service finds the customer's active session
    or creates a new one automatically.

    This means the frontend only needs two fields:
      customer_id + message
    """
    message:     str = Field(..., min_length=1, max_length=2000, description="Customer message")
    customer_id: uuid.UUID | None = Field(None, description="Omit for anonymous/guest")
    session_id:  uuid.UUID | None = Field(None, description="Omit to auto-resolve session")
    channel:     Literal["web", "mobile", "whatsapp", "sdk"] = "web"
    filters:     dict[str, Any] = Field(default_factory=dict, description="Optional RAG filters")

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        return v.strip()


class CustomerCreateRequest(BaseModel):
    external_id: str | None = Field(None, description="Your platform's customer ID")
    email:       str | None = None
    name:        str | None = None
    phone:       str | None = None
    profile:     dict[str, Any] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    rating:        Literal[-1, 1] = Field(..., description="1 = helpful, -1 = not helpful")
    comment:       str | None = Field(None, max_length=1000)
    feedback_type: Literal[
        "helpful", "wrong_product", "bad_link",
        "hallucination", "other"
    ] | None = None


class SessionCreateRequest(BaseModel):
    customer_id: uuid.UUID | None = None
    channel:     Literal["web", "mobile", "whatsapp", "sdk"] = "web"


# ─────────────────────────────────────────────────────────────────────────────
# Outbound DTOs
# ─────────────────────────────────────────────────────────────────────────────

class ProductCardDTO(BaseModel):
    """A product cited in the bot's response."""
    citation_id: str
    title:       str
    url:         str
    price:       float | None
    currency:    str = "USD"
    image_url:   str | None
    sku:         str | None
    in_stock:    bool
    rating:      float | None
    similarity:  float | None = None


class ChatResponse(BaseModel):
    """
    Response from POST /api/v1/chat.

    answer      — plain text, use for accessibility / fallback
    answer_html — text with <a href> product chips, render in chat bubble
    cited_products — product cards to render below the bubble
    suggestions — tappable chips shown below the input box
    """
    message_id:       uuid.UUID
    session_id:       uuid.UUID
    answer:           str
    answer_html:      str
    cited_products:   list[ProductCardDTO]
    suggestions:      list[dict] = Field(default_factory=list, description="Tappable suggestion chips")
    intent:           str
    guardrail_status: Literal["passed", "blocked", "warned"]
    blocked:          bool
    latency_ms:       int
    tokens_used:      int


class SessionResponse(BaseModel):
    id:            uuid.UUID
    customer_id:   uuid.UUID | None
    channel:       str
    status:        str
    message_count: int
    total_tokens:  int
    started_at:    datetime
    ended_at:      datetime | None

    model_config = {"from_attributes": True}


class CustomerResponse(BaseModel):
    id:          uuid.UUID
    external_id: str | None
    email:       str | None
    name:        str | None
    status:      str
    profile:     dict[str, Any]
    created_at:  datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id:             uuid.UUID
    role:           str
    content:        str
    cited_products: list[dict[str, Any]]
    intent:         str | None
    created_at:     datetime

    model_config = {"from_attributes": True}


class FeedbackResponse(BaseModel):
    id:            uuid.UUID
    message_id:    uuid.UUID
    rating:        int
    comment:       str | None
    feedback_type: str | None
    created_at:    datetime

    model_config = {"from_attributes": True}


class MessageHistoryResponse(BaseModel):
    """Cursor-paginated message history."""
    messages:    list[MessageResponse]
    next_cursor: uuid.UUID | None = Field(
        None,
        description="Pass as before_id to get the next page. None means no more pages."
    )
    has_more:    bool


class ErrorResponse(BaseModel):
    error:   str
    detail:  str | None = None
    code:    str | None = None
