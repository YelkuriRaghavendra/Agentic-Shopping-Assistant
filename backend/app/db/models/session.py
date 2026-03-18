"""Session ORM model."""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, SmallInteger, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.models.base import Base, utcnow


class Session(Base):
    __tablename__ = "sessions"

    id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id:   Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    # web | mobile | whatsapp | sdk
    channel:       Mapped[str] = mapped_column(String(50), nullable=False, default="web")
    # active | ended | abandoned | expired
    status:        Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # Layer 2 memory: slots, shown_products, summary, last_intent, known_people
    context:       Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens:  Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at:      Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    customer: Mapped["Customer | None"] = relationship(  # noqa: F821
        back_populates="sessions"
    )
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    feedback: Mapped["SessionFeedback | None"] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sessions_customer_id",  "customer_id"),
        Index("idx_sessions_status",       "status"),
        Index("idx_sessions_updated_at",   "updated_at"),
        Index(
            "idx_sessions_active_customer",
            "customer_id", "status",
            postgresql_where=text("status = 'active'"),
        ),
    )


class SessionFeedback(Base):
    __tablename__ = "session_feedback"

    id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id:    Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # 1 = thumbs up, -1 = thumbs down
    rating:        Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment:       Mapped[str | None] = mapped_column(Text,       nullable=True)
    # helpful | poor_suggestions | inaccurate | bad_experience | other
    feedback_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    session: Mapped["Session"] = relationship(back_populates="feedback")

    __table_args__ = (
        Index("idx_session_feedback_rating", "rating"),
        Index("idx_session_feedback_type",   "feedback_type"),
    )
