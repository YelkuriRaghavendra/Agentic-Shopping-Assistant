from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, DateTime, func
from app.db.session import Base as _Base
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(_Base):
    """
    Abstract base for all RAG-service models.
    Every table automatically gets these audit columns.
    """

    __abstract__ = True

    created_by:      Mapped[str]            = mapped_column(Text, nullable=False)
    last_updated_by: Mapped[str | None]     = mapped_column(Text, nullable=True)
    created_at:      Mapped[datetime]       = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )


__all__ = ["Base", "utcnow"]
