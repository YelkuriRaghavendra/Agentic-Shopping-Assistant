from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ProductIngestRequest(BaseModel):
    source_id: uuid.UUID
    product_id: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    product_description: str
    product_url: str = Field(..., min_length=1)
    price: float = Field(..., ge=0)
    currency: str = Field(default="INR", max_length=3)
    image_url:str
    brand: str | None = None
    category: str | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    customer_reviews: list[str] = Field(default_factory=list)
    product_attributes: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    extra_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_content(self) -> str:
        top_reviews = self.customer_reviews[:3]
        attributes_text = "\n".join(f"  {key}: {value}" for key, value in self.product_attributes.items())
        parts = [
            f"Product_id: {self.product_id}",
            f"Product_name: {self.product_name}",
            f"Brand: {self.brand}" if self.brand else "",
            f"Category: {self.category}" if self.category else "",
            f"Product_description: {self.product_description}",
            f"Price: {self.currency} {self.price}",
            f"Tags: {', '.join(self.tags)}" if self.tags else "",
            f"Rating: {self.rating}/5 ({self.review_count} reviews)" if self.rating else "",
            f"Image URL: {self.image_url}" if self.image_url else "",
            "Product Attributes:\n" + attributes_text if self.product_attributes else "",
            "Customer Reviews:\n" + "\n".join(f"- {review}" for review in top_reviews) if top_reviews else "",
        ]
        return "\n".join(part for part in parts if part)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "product_url": self.product_url,
            "price": self.price,
            "currency": self.currency,
            "brand": self.brand,
            "category": self.category,
            "rating": self.rating,
            "image_url": self.image_url,
            "review_count": self.review_count,
            "customer_reviews": self.customer_reviews,
            "product_attributes": self.product_attributes,
            "tags": self.tags,
            **self.extra_metadata,
        }


class IngestResponse(BaseModel):
    document_id: uuid.UUID
    job_id:      uuid.UUID | None
    status:      str
    message:     str


class BulkProductIngestRequest(BaseModel):
    products: list[ProductIngestRequest] = Field(
        ..., min_length=1, max_length=500,
        description="List of products to ingest (1-500).",
    )


class BulkIngestResponse(BaseModel):
    total: int
    status: str
    message: str


class JobsResponse(BaseModel):
    job_id: uuid.UUID
    document_id: uuid.UUID
    status: str
    chunks_total: int
    chunks_done: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    progress_percentage: float

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, job) -> "JobsResponse":
        percentage = (
            round(job.chunks_done / job.chunks_total * 100, 1)
            if job.chunks_total > 0 else 0.0
        )
        return cls(
            job_id=job.job_id,
            document_id=job.document_id,
            status=job.status,
            chunks_total=job.chunks_total,
            chunks_done=job.chunks_done,
            error_message=job.error_message,
            started_at=job.started_at,
            finished_at=job.finished_at,
            progress_percentage=percentage,
        )
