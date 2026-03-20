"""
Cross-encoder reranking client.

Loads a sentence-transformers CrossEncoder model once (lazy, on first use)
and scores (query, passage) pairs synchronously in a thread-pool so the
async event-loop is never blocked.
"""

import asyncio
from functools import lru_cache

from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _load_model(model_name: str):
    from sentence_transformers import CrossEncoder  # type: ignore[import]
    logger.info("cross_encoder.loading", model=model_name)
    model = CrossEncoder(model_name)
    logger.info("cross_encoder.ready", model=model_name)
    return model


class CrossEncoderClient:
    """
    Scores (query, passage) pairs with a local CrossEncoder model.
    Returns a list of float scores in the same order as the input pairs.
    """

    def __init__(self, model_name: str):
        self._model_name = model_name

    async def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        """
        Score a list of (query, passage) pairs.
        Runs the CPU-bound inference in a thread-pool executor.
        """
        if not pairs:
            return []

        loop = asyncio.get_running_loop()
        scores: list[float] = await loop.run_in_executor(
            None, self._score_sync, pairs
        )
        return scores

    def _score_sync(self, pairs: list[tuple[str, str]]) -> list[float]:
        model = _load_model(self._model_name)
        raw = model.predict(pairs)
        return [float(s) for s in raw]
