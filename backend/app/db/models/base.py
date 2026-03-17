"""Shared base for all ORM models."""
from datetime import datetime, UTC
from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


__all__ = ["Base", "utcnow"]
