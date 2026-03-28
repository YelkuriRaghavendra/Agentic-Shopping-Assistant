"""
Rate limiter service.

Distributed rate limiting using Redis (INCR + EXPIRE).
Falls back to in-memory sliding window if Redis is unavailable.

For multi-instance deployments, all instances share Redis counters.

Limits:
  - Per-customer: N messages per minute
  - Per-customer: N messages per day
"""

import uuid
import time
from collections import defaultdict, deque

from app.clients.redis_client import rate_limit_check
from app.core.config import get_settings
from app.core.exceptions import CustomerRateLimitError
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RateLimiterService:
    """
    Hybrid rate limiter: Redis (distributed) with in-memory fallback.
    """

    def __init__(self):
        # In-memory fallback (used when Redis is unavailable)
        self._minute_window: dict[str, deque] = defaultdict(deque)
        self._day_window: dict[str, deque] = defaultdict(deque)

    async def check(self, customer_id: uuid.UUID | None) -> None:
        """
        Check if the customer is within rate limits.
        Tries Redis first; falls back to in-memory if Redis is down.
        Raises CustomerRateLimitError if limit exceeded.
        """
        key = str(customer_id) if customer_id else "guest"

        # Try Redis-based distributed check
        redis_minute_key = f"rl:min:{key}"
        redis_day_key = f"rl:day:{key}"

        minute_ok, minute_count = await rate_limit_check(
            redis_minute_key, settings.RATE_LIMIT_PER_MINUTE, 60
        )
        if not minute_ok:
            logger.warning(
                "rate_limiter.exceeded",
                customer=key, window="per_minute",
                count=minute_count, limit=settings.RATE_LIMIT_PER_MINUTE,
            )
            raise CustomerRateLimitError(
                "Rate limit exceeded (per_minute). "
                "Please wait a moment before sending another message."
            )

        day_ok, day_count = await rate_limit_check(
            redis_day_key, settings.RATE_LIMIT_PER_DAY, 86400
        )
        if not day_ok:
            logger.warning(
                "rate_limiter.exceeded",
                customer=key, window="per_day",
                count=day_count, limit=settings.RATE_LIMIT_PER_DAY,
            )
            raise CustomerRateLimitError(
                "Rate limit exceeded (per_day). "
                "Please wait before sending another message."
            )

        # If Redis returned (True, 0) it means Redis is down — use in-memory fallback
        if minute_count == 0 and day_count == 0:
            self._check_memory_fallback(key)

    def _check_memory_fallback(self, key: str) -> None:
        """In-memory sliding window fallback when Redis is unavailable."""
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
        cutoff = now - window_seconds
        while window and window[0] < cutoff:
            window.popleft()

        if len(window) >= limit:
            logger.warning(
                "rate_limiter.exceeded",
                customer=key, window=label,
                count=len(window), limit=limit,
            )
            raise CustomerRateLimitError(
                f"Rate limit exceeded ({label}). "
                "Please wait a moment before sending another message."
            )

        window.append(now)
