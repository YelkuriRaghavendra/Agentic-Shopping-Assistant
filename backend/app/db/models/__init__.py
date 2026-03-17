"""
ORM models — import from here everywhere.

Split into one file per table:
  customer.py        → Customer
  session.py         → Session
  message.py         → Message, MessageFeedback

All models must be imported here so SQLAlchemy's mapper
sees them before migrations or Base.metadata is used.
"""

from app.db.models.customer import Customer
from app.db.models.session import Session
from app.db.models.message import Message, MessageFeedback

__all__ = ["Customer", "Session", "Message", "MessageFeedback"]
