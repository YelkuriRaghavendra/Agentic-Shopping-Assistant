"""
Backwards-compatibility shim.
All models have been split into individual files.
Import from app.db.models directly — not from here.
"""
from app.db.models.customer import Customer
from app.db.models.session import Session, SessionFeedback
from app.db.models.message import Message

__all__ = ["Customer", "Session", "SessionFeedback", "Message"]
