"""Base HTTP client — retry, timeout, error handling."""
import httpx
from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseHTTPClient:
    def __init__(self, base_url: str, timeout: float = 30.0, headers: dict | None = None):
        self._base_url = base_url.rstrip("/")
        self._timeout  = httpx.Timeout(timeout)
        self._headers  = {"Content-Type": "application/json", **(headers or {})}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=self._timeout)

    async def _post(self, path: str, payload: dict) -> dict:
        async with self._client() as client:
            try:
                r = await client.post(path, json=payload)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as exc:
                logger.error("http_client.error", path=path, status=exc.response.status_code)
                raise

    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with self._client() as client:
            try:
                r = await client.get(path, params=params)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as exc:
                logger.error("http_client.error", path=path, status=exc.response.status_code)
                raise
