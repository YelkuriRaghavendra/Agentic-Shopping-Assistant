"""
Rate limiter service.

In-process rate limiting using a sliding window counter.
Simple, zero-dependency, good enough for a single instance.

For multi-instance deployments, swap this for Redis-based limiting —
the interface stays the same, only the backend changes.

Limits:
  - Per-customer: N messages per minute
  - Per-customer: N messages per day
"""

import uuid
import time
from collections import defaultdict, deque

from app.core.config import get_settings
from app.core.exceptions import CustomerRateLimitError
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RateLimiterService:
    """
    Sliding window rate limiter.
    Thread-safe for asyncio (single event loop, no shared state issues).
    """

    def __init__(self):
        # customer_id -> deque of timestamps (sliding window)
        self._minute_window: dict[str, deque] = defaultdict(deque)
        self._day_window:    dict[str, deque] = defaultdict(deque)

    def check(self, customer_id: uuid.UUID | None) -> None:
        """
        Check if the customer is within rate limits.
        Raises CustomerRateLimitError if limit exceeded.
        Guest (None) users share a single "guest" bucket.
        """
        key = str(customer_id) if customer_id else "guest"
        now = time.monotonic()

        self._check_window(
            key=key,
            window=self._minute_window[key],
            limit=settings.RATE_LIMIT_PER_MINUTE,
            window_seconds=60,
            now=now,
            label="per_minute",
        )
        self._check_window(
            key=key,
            window=self._day_window[key],
            limit=settings.RATE_LIMIT_PER_DAY,
            window_seconds=86400,
            now=now,
            label="per_day",
        )

    def _check_window(
        self,
        key: str,
        window: deque,
        limit: int,
        window_seconds: float,
        now: float,
        label: str,
    ) -> None:
        # Remove timestamps older than the window
        cutoff = now - window_seconds
        while window and window[0] < cutoff:
            window.popleft()

        if len(window) >= limit:
            logger.warning(
                "rate_limiter.exceeded",
                customer=key,
                window=label,
                count=len(window),
                limit=limit,
            )
            raise CustomerRateLimitError(
                f"Rate limit exceeded ({label}). "
                "Please wait a moment before sending another message."
            )

        window.append(now)
