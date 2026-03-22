"""Message ORM model."""
import uuid
from sqlalchemy import String, Text, Integer, ForeignKey, Index, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.models.base import Base
from app.db.models.enums.message_enums import MessageRole, GuardrailStatus


class Message(Base):
    __tablename__ = "messages"

    message_id:       Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id:       Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    role:             Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, name="message_role_enum"),
        nullable=False,
    )
    content:          Mapped[str] = mapped_column(Text, nullable=False)
    intent:           Mapped[str | None] = mapped_column(String(50), nullable=True)
    guardrail_status: Mapped[GuardrailStatus | None] = mapped_column(
        SAEnum(GuardrailStatus, name="guardrail_status_enum"),
        nullable=True,
    )
    guardrail_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cited_products:   Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    input_tokens:     Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms:       Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_model:        Mapped[str | None] = mapped_column(String(50), nullable=True)

    session: Mapped["Session"] = relationship(back_populates="messages")  # noqa: F821

    __table_args__ = (
        Index("idx_messages_session_id", "session_id"),
        Index("idx_messages_intent",     "intent"),
        Index("idx_messages_cited",      "cited_products", postgresql_using="gin"),
    )
