"""Customer ORM model."""
import uuid
from sqlalchemy import String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.models.base import Base, utcnow
from datetime import datetime


class Customer(Base):
    __tablename__ = "customers"

    id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    email:       Mapped[str | None] = mapped_column(String(255), nullable=True)
    name:        Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone:       Mapped[str | None] = mapped_column(String(50),  nullable=True)
    # Layer 3 memory: preferred_brands, usual_sizes, price_sensitivity, known_people
    profile:     Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # active | blocked | guest
    status:      Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        back_populates="customer", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_customers_external_id", "external_id"),
        Index("idx_customers_email",       "email"),
        Index("idx_customers_status",      "status"),
    )
