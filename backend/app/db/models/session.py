"""Session ORM model."""
import uuid
from datetime import datetime
from sqlalchemy import Integer, SmallInteger, DateTime, ForeignKey, Index, Text, String, text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.models.base import Base, utcnow
from app.db.models.enums.session_enums import SessionStatus, ChannelType, FeedbackType


class Session(Base):
    __tablename__ = "sessions"

    session_id:    Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id:   Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id", ondelete="SET NULL"), nullable=True
    )
    channel:       Mapped[ChannelType] = mapped_column(
        SAEnum(ChannelType, name="channel_type_enum"),
        nullable=False, default=ChannelType.WEB,
    )
    status:        Mapped[SessionStatus] = mapped_column(
        SAEnum(SessionStatus, name="session_status_enum"),
        nullable=False, default=SessionStatus.ACTIVE,
    )
    # Layer 2 memory: slots, shown_products, summary, last_intent, known_people
    context:       Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens:  Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    ended_at:      Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
        Index("idx_sessions_active_customer",
              "customer_id", "status",
              postgresql_where=text("status = 'active'")),
    )


class SessionFeedback(Base):
    __tablename__ = "session_feedback"

    session_feedback_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id:    Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # 1 = thumbs up, -1 = thumbs down
    rating:        Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment:       Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_type: Mapped[FeedbackType | None] = mapped_column(
        SAEnum(FeedbackType, name="feedback_type_enum"),
        nullable=True,
    )

    session: Mapped["Session"] = relationship(back_populates="feedback")

    __table_args__ = (
        Index("idx_session_feedback_rating", "rating"),
        Index("idx_session_feedback_type",   "feedback_type"),
    )
