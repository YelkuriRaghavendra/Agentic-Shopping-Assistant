"""Customer ORM model."""
import uuid
from sqlalchemy import String, Index, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.models.base import Base
from app.db.models.enums.customer_enums import CustomerStatus


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    email:       Mapped[str | None] = mapped_column(String(255), nullable=True)
    name:        Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone:       Mapped[str | None] = mapped_column(String(50),  nullable=True)
    profile:     Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status:      Mapped[CustomerStatus] = mapped_column(
        SAEnum(CustomerStatus, name="customer_status_enum"),
        nullable=False, default=CustomerStatus.ACTIVE,
    )

    sessions: Mapped[list["Session"]] = relationship(  # noqa: F821
        back_populates="customer", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_customers_external_id", "external_id"),
        Index("idx_customers_email",       "email"),
        Index("idx_customers_status",      "status"),
    )
