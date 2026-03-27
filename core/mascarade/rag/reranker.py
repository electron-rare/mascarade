"""Cross-encoder reranking for RAG — wraps BAAI/bge-reranker-v2-m3.

Install the optional dep:
    pip install mascarade-core[reranker]

Falls back silently (original order kept) when sentence-transformers is absent.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger("mascarade.rag.reranker")

# Single-thread executor: cross-encoder predict() is CPU-bound, one at a time is fine.
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor  # noqa: PLW0603
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reranker")
    return _executor


class CrossEncoderReranker:
    """Thin async wrapper around sentence-transformers CrossEncoder.

    Lazy-loads the model on first use.  If sentence-transformers is not
    installed the reranker silently returns the original list (no crash).

    Usage::

        reranker = CrossEncoderReranker()
        results = await reranker.rerank(query, results, top_k=5)
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        self._model_name = model_name
        self._model: Any = None
        self._available: bool | None = None  # None = not yet probed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Async cross-encoder rerank.  Returns top_k results sorted by score."""
        if not results:
            return results
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _get_executor(),
            self._sync_rerank,
            query,
            list(results),  # copy — don't mutate caller's list
            top_k,
        )

    @property
    def is_available(self) -> bool:
        """True if sentence-transformers + model are loadable."""
        self._ensure_loaded()
        return self._available is True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._available is not None:
            return
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]

            self._model = CrossEncoder(self._model_name)
            self._available = True
            logger.info("Cross-encoder loaded: %s", self._model_name)
        except ImportError:
            logger.info(
                "sentence-transformers not installed — cross-encoder reranking disabled. "
                "Enable with: pip install mascarade-core[reranker]"
            )
            self._available = False
        except Exception as exc:
            logger.warning("Failed to load cross-encoder %r: %s", self._model_name, exc)
            self._available = False

    def _sync_rerank(
        self, query: str, results: list[dict[str, Any]], top_k: int
    ) -> list[dict[str, Any]]:
        """Blocking rerank — runs inside a thread executor."""
        self._ensure_loaded()
        if not self._available or self._model is None:
            return results[:top_k]

        pairs = [(query, r.get("text", "")[:512]) for r in results]
        scores = self._model.predict(pairs)
        for r, score in zip(results, scores, strict=False):
            r["rerank_score"] = float(score)
        results.sort(key=lambda r: r.get("rerank_score", 0.0), reverse=True)
        return results[:top_k]
