"""Message ORM model."""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.models.base import Base, utcnow


class Message(Base):
    __tablename__ = "messages"

    id:               Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id:       Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    # user | assistant | system
    role:             Mapped[str] = mapped_column(String(20),  nullable=False)
    content:          Mapped[str] = mapped_column(Text,        nullable=False)
    intent:           Mapped[str | None] = mapped_column(String(50),  nullable=True)
    # passed | blocked | warned
    guardrail_status: Mapped[str | None] = mapped_column(String(20),  nullable=True)
    guardrail_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # [{citation_id, title, url, price, sku, image_url, in_stock}]
    cited_products:   Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    input_tokens:     Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms:       Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_model:        Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at:       Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    session: Mapped["Session"] = relationship(back_populates="messages")  # noqa: F821

    __table_args__ = (
        Index("idx_messages_session_id", "session_id"),
        Index("idx_messages_created_at", "created_at"),
        Index("idx_messages_intent",     "intent"),
        Index("idx_messages_cited",      "cited_products", postgresql_using="gin"),
    )
