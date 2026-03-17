"""
Suggestion DTOs.

Typing suggestions appear as chips the customer can tap
instead of typing. Reduces friction, improves conversion.

Examples:
  Customer types "I want" → suggestions: ["running shoes", "casual sneakers", "a jacket"]
  Customer types "Nike"   → suggestions: ["Nike Air Max", "Nike running shoes", "Nike size guide"]
  Bot shows products      → suggestions: ["Compare these", "Show me in size 10", "What about in black?"]
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class SuggestionChip(BaseModel):
    """
    A single tappable suggestion chip.

    label     — what the customer sees (short, max 40 chars)
    message   — what gets sent when tapped (can be longer)
    icon      — optional emoji prefix shown before label
    chip_type — visual style hint for the frontend
    """

    label:     str = Field(..., max_length=40)
    message:   str = Field(..., max_length=500)
    icon:      str | None = None
    chip_type: Literal[
        "quick_reply",   # short follow-up question
        "refine",        # filter/narrow the search
        "action",        # do something (compare, save, share)
        "navigate",      # go somewhere (view cart, track order)
    ] = "quick_reply"


class SuggestionResponse(BaseModel):
    """Returned alongside every ChatResponse."""
    chips: list[SuggestionChip] = Field(default_factory=list)
