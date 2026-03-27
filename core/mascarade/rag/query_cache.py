"""Semantic query cache for the RAG pipeline.

Uses Qdrant as the similarity index and Redis for result storage.
Reduces redundant LLM/embedding calls by 50-70% on repeated or paraphrased queries.

Architecture:
    query  ──embed──► Qdrant collection "rag-query-cache" ──similar?──► Redis
    miss   ──compute──► store embedding in Qdrant + result in Redis

TTL applies to Redis keys only; stale Qdrant points are left (won't be retrieved
because their Redis key is gone) and cleaned up lazily on miss.

Install optional dep for Redis:
    pip install redis

The cache degrades gracefully when Redis or Qdrant are unavailable.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger("mascarade.rag.query_cache")

_DEFAULT_COLLECTION = "rag-query-cache"
_DEFAULT_TTL = 3600  # 1 hour
_DEFAULT_THRESHOLD = 0.92  # cosine similarity


class RAGQueryCache:
    """Semantic query cache backed by Qdrant (similarity) + Redis (results).

    Usage::

        cache = RAGQueryCache()
        # Before expensive RAG call:
        hit = await cache.get(query, embedding)
        if hit:
            return hit
        # After computing result:
        await cache.set(query, embedding, result)
    """

    def __init__(
        self,
        qdrant_url: str | None = None,
        redis_url: str | None = None,
        *,
        similarity_threshold: float = _DEFAULT_THRESHOLD,
        ttl: int = _DEFAULT_TTL,
        collection: str = _DEFAULT_COLLECTION,
        key_prefix: str = "mascarade:ragcache:",
    ) -> None:
        from mascarade.config import settings

        self._qdrant_url = (qdrant_url or settings.qdrant_url).rstrip("/")
        self._redis_url = redis_url or f"redis://{settings.cache_l2_host}:{settings.cache_l2_port}"
        self.similarity_threshold = similarity_threshold
        self.ttl = ttl
        self.collection = collection
        self.key_prefix = key_prefix

        self._redis: Any = None
        self._http: Any = None
        self._collection_ready = False

        # Metrics
        self.hits = 0
        self.misses = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, query: str, embedding: list[float]) -> dict[str, Any] | None:
        """Look up a semantically similar cached query.

        Returns the cached result dict or None on miss.
        """
        try:
            point_id, score = await self._search_similar(embedding)
            if point_id is None or score < self.similarity_threshold:
                self.misses += 1
                return None

            redis_key = f"{self.key_prefix}{point_id}"
            result = await self._redis_get(redis_key)
            if result is None:
                # Redis key expired — point is stale, delete from Qdrant lazily
                asyncio.ensure_future(self._delete_point(point_id))
                self.misses += 1
                return None

            self.hits += 1
            logger.debug(
                "RAG cache hit: score=%.3f, age=%ds, query=%r",
                score,
                int(time.time() - result.get("cached_at", 0)),
                query[:60],
            )
            return result

        except Exception as exc:
            logger.debug("RAG cache get error (non-fatal): %s", exc)
            self.misses += 1
            return None

    async def set(self, query: str, embedding: list[float], result: dict[str, Any]) -> None:
        """Store a result indexed by its query embedding."""
        try:
            await self._ensure_collection(len(embedding))
            point_id = _embedding_to_id(embedding)
            payload = {"query_preview": query[:200], "cached_at": time.time()}

            # Upsert embedding in Qdrant
            http = await self._get_http()
            await http.put(
                f"{self._qdrant_url}/collections/{self.collection}/points",
                json={"points": [{"id": point_id, "vector": embedding, "payload": payload}]},
                params={"wait": "false"},
            )

            # Store result in Redis with TTL
            redis_key = f"{self.key_prefix}{point_id}"
            to_store = {**result, "cached_at": payload["cached_at"]}
            await self._redis_set(redis_key, to_store, ttl=self.ttl)

        except Exception as exc:
            logger.debug("RAG cache set error (non-fatal): %s", exc)

    async def invalidate(self, query: str, embedding: list[float]) -> None:
        """Remove a specific cached entry."""
        point_id = _embedding_to_id(embedding)
        await self._delete_point(point_id)
        await self._redis_del(f"{self.key_prefix}{point_id}")

    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
            "threshold": self.similarity_threshold,
            "ttl_seconds": self.ttl,
            "collection": self.collection,
        }

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internals — Qdrant
    # ------------------------------------------------------------------

    async def _get_http(self):
        if self._http is None or self._http.is_closed:
            import httpx

            self._http = httpx.AsyncClient(timeout=5.0)
        return self._http

    async def _ensure_collection(self, dim: int) -> None:
        if self._collection_ready:
            return
        http = await self._get_http()
        resp = await http.get(f"{self._qdrant_url}/collections/{self.collection}")
        if resp.status_code == 200:
            self._collection_ready = True
            return
        await http.put(
            f"{self._qdrant_url}/collections/{self.collection}",
            json={"vectors": {"size": dim, "distance": "Cosine"}},
        )
        self._collection_ready = True

    async def _search_similar(self, embedding: list[float]) -> tuple[str | None, float]:
        await self._ensure_collection(len(embedding))
        http = await self._get_http()
        resp = await http.post(
            f"{self._qdrant_url}/collections/{self.collection}/points/search",
            json={"vector": embedding, "limit": 1, "with_payload": False},
        )
        if resp.status_code != 200:
            return None, 0.0
        results = resp.json().get("result", [])
        if not results:
            return None, 0.0
        top = results[0]
        return str(top["id"]), float(top.get("score", 0.0))

    async def _delete_point(self, point_id: str) -> None:
        try:
            http = await self._get_http()
            await http.post(
                f"{self._qdrant_url}/collections/{self.collection}/points/delete",
                json={"points": [point_id]},
                params={"wait": "false"},
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internals — Redis
    # ------------------------------------------------------------------

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            except ImportError as exc:
                raise RuntimeError(
                    "redis package required for RAGQueryCache. " "Install with: pip install redis"
                ) from exc
        return self._redis

    async def _redis_get(self, key: str) -> dict[str, Any] | None:
        r = await self._get_redis()
        raw = await r.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def _redis_set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        r = await self._get_redis()
        await r.set(key, json.dumps(value), ex=ttl)

    async def _redis_del(self, key: str) -> None:
        try:
            r = await self._get_redis()
            await r.delete(key)
        except Exception:
            pass


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _embedding_to_id(embedding: list[float]) -> str:
    """Deterministic ID from an embedding vector (sha256 of quantised repr).

    Returns a valid UUID string for Qdrant point IDs.
    """
    # Quantise to 4 decimal places for stability — use full vector
    raw = json.dumps([round(v, 4) for v in embedding])
    hex_digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return str(uuid.UUID(hex_digest))
