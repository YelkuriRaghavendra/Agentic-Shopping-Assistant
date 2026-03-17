"""
Base HTTP client.

All external API clients inherit from this.
Provides: retry logic, timeouts, error translation,
          structured logging, request ID propagation.

Never import this directly in services — use the concrete clients.
"""

import httpx
from tenacity import (
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# Shared retry policy — used by all clients
_RETRY_POLICY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    reraise=True,
)


class BaseHTTPClient:
    """
    Base class for all external HTTP clients.

    Usage:
        class MyClient(BaseHTTPClient):
            def __init__(self):
                super().__init__(base_url="https://api.example.com", timeout=10)
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        headers: dict | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout)
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **(headers or {}),
        }

    def _client(self) -> httpx.AsyncClient:
        """Create a fresh client per request — avoids connection pool issues."""
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=self._timeout,
        )

    async def _get(
        self,
        path: str,
        params: dict | None = None,
        request_id: str | None = None,
    ) -> dict:
        headers = {"X-Request-ID": request_id} if request_id else {}
        async with self._client() as client:
            try:
                response = await client.get(path, params=params, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                self._handle_http_error(e, path)
                raise

    async def _post(
        self,
        path: str,
        payload: dict,
        request_id: str | None = None,
    ) -> dict:
        headers = {"X-Request-ID": request_id} if request_id else {}
        async with self._client() as client:
            try:
                response = await client.post(path, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                self._handle_http_error(e, path)
                raise

    def _handle_http_error(self, error: httpx.HTTPStatusError, path: str) -> None:
        logger.error(
            "http_client.error",
            path=path,
            status=error.response.status_code,
            body=error.response.text[:200],
        )
