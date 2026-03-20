"""
Embedding client.

Wraps OpenAI (or Azure OpenAI) embeddings API.
Services never import openai directly — they use this.

Supports:
  - Batched calls (config-driven batch size)
  - Automatic retry on rate limits
  - Single-query convenience method
"""

import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import openai
from openai import AsyncOpenAI, AsyncAzureOpenAI

from app.core.config import get_settings
from app.config.loader import INGESTION_CONFIG
from app.core.logging import get_logger

settings = get_settings()
logger   = get_logger(__name__)


def _build_client():
    if settings.USE_AZURE:
        return AsyncAzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


_client = _build_client()


class EmbeddingClient:
    """All embedding calls go through this class."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(openai.RateLimitError),
        reraise=True,
    )
    async def _call_batch(self, texts: list[str], dimensions: int) -> list[list[float]]:
        response = await _client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=texts,
            dimensions=dimensions,
            encoding_format="float",
        )
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

    async def embed_texts(self, texts: list[str], dimensions: int) -> list[list[float]]:
        """Embed a list of texts. Batches automatically."""
        if not texts:
            return []
        batch_size = INGESTION_CONFIG["embedding"]["batch_size"]
        results:   list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            logger.debug("embedding.batch", n=len(batch), offset=i)
            try:
                results.extend(await self._call_batch(batch, dimensions))
            except openai.APIError as exc:
                logger.error("embedding.api_error", error=str(exc))
                raise
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)
        return results

    async def embed_single(self, text: str, dimensions: int) -> list[float]:
        """Embed one string — used at query time."""
        return (await self.embed_texts([text], dimensions))[0]
