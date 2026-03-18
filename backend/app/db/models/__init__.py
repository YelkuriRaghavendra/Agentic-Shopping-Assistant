"""
ORM models — import from here everywhere.

Split into one file per table:
  customer.py        → Customer
  session.py         → Session, SessionFeedback
  message.py         → Message

All models must be imported here so SQLAlchemy's mapper
sees them before migrations or Base.metadata is used.
"""

from app.db.models.customer import Customer
from app.db.models.session import Session, SessionFeedback
from app.db.models.message import Message

__all__ = ["Customer", "Session", "SessionFeedback", "Message"]
