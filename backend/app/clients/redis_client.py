"""
Redis client — shared connection pool for caching and rate limiting.

Falls back gracefully if Redis is unavailable:
  - Cache misses → proceeds without cache
  - Rate limiting → falls back to in-memory
  - No crash, no error to user

Usage:
    from app.clients.redis_client import get_redis, cache_get, cache_set

    value = await cache_get("key")
    await cache_set("key", value, ttl=300)
"""

import json
import hashlib
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

_pool: redis.Redis | None = None


async def init_redis() -> None:
    """Initialize Redis connection pool. Call once at app startup."""
    global _pool
    if not settings.REDIS_ENABLED:
        logger.info("redis.disabled")
        return
    try:
        _pool = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
        await _pool.ping()
        logger.info("redis.connected", url=settings.REDIS_URL.split("@")[-1])
    except Exception as exc:
        logger.warning("redis.connect_failed", error=str(exc))
        _pool = None


async def close_redis() -> None:
    """Close Redis pool. Call at app shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_redis() -> redis.Redis | None:
    """Get the Redis connection pool. Returns None if unavailable."""
    return _pool


def make_cache_key(*parts: str) -> str:
    """Build a deterministic cache key from parts."""
    raw = ":".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def cache_get(key: str) -> Any | None:
    """Get a value from Redis cache. Returns None on miss or error."""
    if not _pool:
        return None
    try:
        data = await _pool.get(key)
        if data is None:
            return None
        return json.loads(data)
    except Exception as exc:
        logger.debug("cache.get_failed", key=key, error=str(exc))
        return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """Set a value in Redis cache with TTL. Silent on error."""
    if not _pool:
        return
    try:
        await _pool.setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:
        logger.debug("cache.set_failed", key=key, error=str(exc))


async def cache_delete(key: str) -> None:
    """Delete a cache key. Silent on error."""
    if not _pool:
        return
    try:
        await _pool.delete(key)
    except Exception as exc:
        logger.debug("cache.delete_failed", key=key, error=str(exc))


async def rate_limit_check(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """
    Distributed rate limit check using Redis INCR + EXPIRE.

    Returns:
        (allowed: bool, current_count: int)
    """
    if not _pool:
        return True, 0  # fallback: allow if Redis down
    try:
        pipe = _pool.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = await pipe.execute()

        # Set expiry on first request in window
        if ttl == -1:
            await _pool.expire(key, window_seconds)

        return count <= limit, count
    except Exception as exc:
        logger.debug("rate_limit.check_failed", key=key, error=str(exc))
        return True, 0  # fallback: allow
