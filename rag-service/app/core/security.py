"""
API key authentication dependency.

Reads the key from the X-API-Key header and compares it against
the configured API_KEY. If API_KEY is empty, authentication is
skipped (development mode).
"""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import get_settings

settings = get_settings()

_api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str | None:
    """
    FastAPI dependency that enforces API key authentication.
    If no API_KEY is configured (empty string), all requests are allowed.
    """
    if not settings.API_KEY:
        # No key configured — skip auth (dev mode)
        return None
    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return api_key
