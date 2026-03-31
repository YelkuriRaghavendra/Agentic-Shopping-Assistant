"""
DTOs for the order embedding event endpoint.

The checkout-order-service POSTs to /api/v1/orders/index whenever:
  - An order.confirmed event fires (new order)
  - An order status changes (re-index within 5 minutes)
"""
from __future__ import annotations
import uuid
from typing import Any
from pydantic import BaseModel, Field


class OrderEventRequest(BaseModel):
    """Payload sent by checkout-order-service to trigger order (re-)indexing."""

    source_id:   uuid.UUID = Field(..., description="RAG source UUID for order documents")
    customer_id: str       = Field(..., min_length=1, description="Customer UUID — scopes the embedding")
    order: dict[str, Any]  = Field(..., description="Full order payload from checkout-order-service")


class OrderIndexResponse(BaseModel):
    document_id: uuid.UUID
    job_id:      uuid.UUID | None
    status:      str
    message:     str
