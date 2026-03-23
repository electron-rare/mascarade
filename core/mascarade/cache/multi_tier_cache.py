"""Multi-tier cache orchestrator for LLM responses.

This module implements a three-tier caching strategy:
- L1: In-memory LRU cache (fast, limited capacity)
- L2: Redis persistent cache (medium speed, larger capacity)
- L3: Semantic cache using GPTCache (slow, similarity-based)

The cache tries each tier in order on retrieval (L1 → L2 → L3) and backfills
faster tiers when finding data in slower tiers to improve future hit rates.
"""

from __future__ import annotations

import logging
from typing import Any

from mascarade.cache.cache import CacheBackend, CacheEntry, InMemoryCache

logger = logging.getLogger(__name__)


class MultiTierCache:
    """
    Multi-tier cache orchestrator with L1/L2/L3 strategy.

    Coordinates between in-memory (L1), Redis (L2), and semantic (L3) caches
    to maximize hit rate while maintaining performance.

    Example:
        >>> from mascarade.cache.redis_cache import RedisCache
        >>> from mascarade.cache.semantic_cache import SemanticCache
        >>>
        >>> cache = MultiTierCache(
        ...     l1=InMemoryCache(max_size=1000),
        ...     l2=RedisCache(),
        ...     l3=SemanticCache(similarity_threshold=0.85)
        ... )
        >>>
        >>> # Store in all tiers
        >>> await cache.store(
        ...     messages=[{"role": "user", "content": "Hello"}],
        ...     response="Hi there!",
        ...     tokens=10,
        ...     cost=0.0001
        ... )
        >>>
        >>> # Retrieve tries L1 → L2 → L3
        >>> entry = await cache.retrieve(
        ...     messages=[{"role": "user", "content": "Hello"}]
        ... )
    """

    def __init__(
        self,
        l1: InMemoryCache | None = None,
        l2: CacheBackend | None = None,
        l3: CacheBackend | None = None,
    ) -> None:
        """
        Initialize multi-tier cache.

        Args:
            l1: L1 in-memory cache (default: InMemoryCache with max_size=1000)
            l2: L2 Redis cache (optional, None disables L2)
            l3: L3 semantic cache (optional, None disables L3)
        """
        self.l1 = l1 or InMemoryCache(max_size=1000)
        self.l2 = l2
        self.l3 = l3

        # Track which tiers are available
        self.l2_available = l2 is not None
        self.l3_available = l3 is not None

        logger.info(
            f"MultiTierCache initialized: L1=enabled, L2={'enabled' if self.l2_available else 'disabled'}, "
            f"L3={'enabled' if self.l3_available else 'disabled'}"
        )

    @property
    def tiers(self) -> dict[str, CacheBackend | None]:
        """
        Get dictionary of all cache tiers.

        Returns:
            Dictionary mapping tier names to cache backend instances:
            {"L1": InMemoryCache, "L2": RedisCache | None, "L3": SemanticCache | None}
        """
        return {"L1": self.l1, "L2": self.l2, "L3": self.l3}

    async def store(
        self,
        messages: list[dict],
        response: str,
        tokens: int,
        cost: float,
        ttl: float = 3600,
        **kwargs: dict[str, str | int | float | None],
    ) -> str:
        """
        Store a response in all available cache tiers.

        Stores in L1, L2, and L3 concurrently to ensure consistency.
        Failures in L2/L3 are logged but don't prevent L1 storage.

        Args:
            messages: The LLM messages that were sent
            response: The LLM response content
            tokens: Number of tokens used
            cost: Cost of the request
            ttl: Time-to-live in seconds (default: 3600)
            **kwargs: Additional metadata (strategy, provider, model, etc.)

        Returns:
            The cache key used to store the entry
        """
        # Store in L1 (sync, always available)
        key = self.l1.store(messages, response, tokens, cost, ttl, **kwargs)

        # Store in L2 (async, if available)
        if self.l2_available and self.l2:
            try:
                await self.l2.store(messages, response, tokens, cost, ttl, **kwargs)
                logger.debug("MultiTierCache: stored in L2 (Redis)")
            except Exception as e:
                logger.warning(f"MultiTierCache: L2 store failed, degrading to L1 only: {e}")
                self.l2_available = False

        # Store in L3 (async, if available)
        if self.l3_available and self.l3:
            try:
                await self.l3.store(messages, response, tokens, cost, ttl, **kwargs)
                logger.debug("MultiTierCache: stored in L3 (Semantic)")
            except Exception as e:
                logger.warning(f"MultiTierCache: L3 store failed: {e}")
                # L3 failures are expected (optional), don't disable tier

        return key

    async def retrieve(
        self, messages: list[dict], **kwargs: dict[str, str | int | float | None]
    ) -> CacheEntry | None:
        """
        Retrieve a cached response from L1 → L2 → L3.

        Tries each tier in order. On L2/L3 hit, backfills faster tiers
        to improve future hit rates.

        Args:
            messages: The LLM messages to look up
            **kwargs: Additional metadata for cache key generation

        Returns:
            CacheEntry if found in any tier, None otherwise
        """
        # Try L1 (in-memory, fastest)
        entry = self.l1.retrieve(messages, **kwargs)
        if entry:
            logger.debug("MultiTierCache: L1 hit")
            return entry

        # Try L2 (Redis, medium speed)
        if self.l2_available and self.l2:
            try:
                entry = await self.l2.retrieve(messages, **kwargs)
                if entry:
                    logger.debug("MultiTierCache: L2 hit, backfilling L1")
                    # Backfill L1 for faster future access
                    self._backfill_l1(messages, entry, **kwargs)
                    return entry
            except Exception as e:
                logger.warning(f"MultiTierCache: L2 retrieve failed, degrading: {e}")
                self.l2_available = False

        # Try L3 (Semantic, slowest but similarity-based)
        if self.l3_available and self.l3:
            try:
                entry = await self.l3.retrieve(messages, **kwargs)
                if entry:
                    logger.debug("MultiTierCache: L3 hit, backfilling L1 and L2")
                    # Backfill L1 and L2 for faster future access
                    self._backfill_l1(messages, entry, **kwargs)
                    await self._backfill_l2(messages, entry, **kwargs)
                    return entry
            except Exception as e:
                logger.warning(f"MultiTierCache: L3 retrieve failed: {e}")
                # L3 failures are expected (optional), don't disable tier

        logger.debug("MultiTierCache: miss on all tiers")
        return None

    def _backfill_l1(
        self,
        messages: list[dict],
        entry: CacheEntry,
        **kwargs: dict[str, str | int | float | None],
    ) -> None:
        """
        Backfill L1 cache with entry from L2/L3.

        Args:
            messages: The LLM messages
            entry: The cache entry to backfill
            **kwargs: Additional metadata
        """
        try:
            self.l1.store(
                messages=messages,
                response=entry.response,
                tokens=entry.tokens,
                cost=entry.cost,
                ttl=entry.ttl,
                strategy=entry.strategy,
                provider=entry.provider,
                model=entry.model,
                **kwargs,
            )
        except Exception as e:
            logger.warning(f"MultiTierCache: L1 backfill failed: {e}")

    async def _backfill_l2(
        self,
        messages: list[dict],
        entry: CacheEntry,
        **kwargs: dict[str, str | int | float | None],
    ) -> None:
        """
        Backfill L2 cache with entry from L3.

        Args:
            messages: The LLM messages
            entry: The cache entry to backfill
            **kwargs: Additional metadata
        """
        if not self.l2_available or not self.l2:
            return

        try:
            await self.l2.store(
                messages=messages,
                response=entry.response,
                tokens=entry.tokens,
                cost=entry.cost,
                ttl=entry.ttl,
                strategy=entry.strategy,
                provider=entry.provider,
                model=entry.model,
                **kwargs,
            )
        except Exception as e:
            logger.warning(f"MultiTierCache: L2 backfill failed: {e}")
            self.l2_available = False

    async def get_stats(self) -> dict[str, Any]:
        """
        Get aggregated cache statistics from all tiers.

        Returns:
            Dictionary with per-tier stats and overall metrics:
            {
                "tiers": {
                    "L1": {...},
                    "L2": {...},
                    "L3": {...}
                },
                "overall": {
                    "total_hits": int,
                    "total_misses": int,
                    "combined_hit_rate": float
                },
                "available_tiers": ["L1", "L2", "L3"],
                "degraded": bool
            }
        """
        stats: dict[str, Any] = {
            "tiers": {},
            "overall": {},
            "available_tiers": [],
            "degraded": False,
        }

        # L1 stats (always available, sync)
        try:
            l1_stats = self.l1.get_stats()
            stats["tiers"]["L1"] = {**l1_stats, "tier": "L1", "type": "in-memory"}
            stats["available_tiers"].append("L1")
        except Exception as e:
            logger.error(f"MultiTierCache: L1 stats failed: {e}")
            stats["tiers"]["L1"] = {"tier": "L1", "error": str(e)}

        # L2 stats (async, if available)
        if self.l2_available and self.l2:
            try:
                l2_stats = await self.l2.get_stats()
                stats["tiers"]["L2"] = {**l2_stats, "tier": "L2", "type": "redis"}
                stats["available_tiers"].append("L2")
            except Exception as e:
                logger.warning(f"MultiTierCache: L2 stats failed: {e}")
                stats["tiers"]["L2"] = {"tier": "L2", "error": str(e)}
                stats["degraded"] = True
        else:
            stats["tiers"]["L2"] = {"tier": "L2", "status": "disabled"}
            stats["degraded"] = True

        # L3 stats (async/sync depending on implementation)
        if self.l3_available and self.l3:
            try:
                # SemanticCache.get_stats() is sync
                l3_stats = self.l3.get_stats()
                stats["tiers"]["L3"] = {**l3_stats, "tier": "L3"}
                stats["available_tiers"].append("L3")
            except Exception as e:
                logger.warning(f"MultiTierCache: L3 stats failed: {e}")
                stats["tiers"]["L3"] = {"tier": "L3", "error": str(e)}
        else:
            stats["tiers"]["L3"] = {"tier": "L3", "status": "disabled"}

        # Calculate overall stats
        total_hits = sum(
            tier_stats.get("hit_count", 0)
            for tier_stats in stats["tiers"].values()
            if isinstance(tier_stats, dict)
        )
        total_misses = sum(
            tier_stats.get("miss_count", 0)
            for tier_stats in stats["tiers"].values()
            if isinstance(tier_stats, dict)
        )
        combined_hit_rate = (
            (total_hits / (total_hits + total_misses)) * 100
            if (total_hits + total_misses) > 0
            else 0
        )

        stats["overall"] = {
            "total_hits": total_hits,
            "total_misses": total_misses,
            "combined_hit_rate": round(combined_hit_rate, 2),
        }

        # Add top-level convenience keys for backward compatibility
        stats["hit_count"] = total_hits
        stats["miss_count"] = total_misses

        return stats

    async def clear(self) -> None:
        """Clear all cache entries in all tiers."""
        # Clear L1 (sync)
        try:
            self.l1.clear()
            logger.info("MultiTierCache: L1 cleared")
        except Exception as e:
            logger.error(f"MultiTierCache: L1 clear failed: {e}")

        # Clear L2 (async, if available)
        if self.l2_available and self.l2:
            try:
                await self.l2.clear()
                logger.info("MultiTierCache: L2 cleared")
            except Exception as e:
                logger.warning(f"MultiTierCache: L2 clear failed: {e}")

        # Clear L3 (sync, if available)
        if self.l3_available and self.l3:
            try:
                self.l3.clear()
                logger.info("MultiTierCache: L3 cleared")
            except Exception as e:
                logger.warning(f"MultiTierCache: L3 clear failed: {e}")

    async def close(self) -> None:
        """Close connections to all cache backends."""
        # L1 doesn't need cleanup (in-memory)

        # Close L2 (Redis connection)
        if self.l2_available and self.l2 and hasattr(self.l2, "close"):
            try:
                await self.l2.close()
                logger.info("MultiTierCache: L2 connection closed")
            except Exception as e:
                logger.warning(f"MultiTierCache: L2 close failed: {e}")

        # L3 doesn't currently need cleanup (SQLite auto-closes)
        # But call if method exists for future compatibility
        if self.l3_available and self.l3 and hasattr(self.l3, "close"):
            try:
                close_method = self.l3.close
                if callable(close_method):
                    # Check if async
                    import inspect

                    if inspect.iscoroutinefunction(close_method):
                        await close_method()
                    else:
                        close_method()
                logger.info("MultiTierCache: L3 connection closed")
            except Exception as e:
                logger.warning(f"MultiTierCache: L3 close failed: {e}")
