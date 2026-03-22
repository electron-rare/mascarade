"""Redis-backed L2 cache for LLM responses."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any

import redis.asyncio as aioredis

from mascarade.cache.cache import CacheBackend, CacheEntry

logger = logging.getLogger(__name__)


class RedisCache(CacheBackend):
    """Redis L2 cache with async operations and TTL support."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
        default_ttl: int = 3600,
        key_prefix: str = "mascarade:cache:",
    ) -> None:
        """Initialize Redis cache.

        Args:
            host: Redis host (default: localhost)
            port: Redis port (default: 6379)
            password: Redis password (optional)
            db: Redis database (default: 0)
            default_ttl: Default TTL in seconds (default: 3600 = 1 hour)
            key_prefix: Prefix for all Redis keys (default: "mascarade:cache:")
        """
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            self.redis_url = redis_url
        else:
            redis_parts = []
            if password:
                redis_parts.append(f":{password}@")
            redis_parts.append(f"{host}:{port}")
            redis_parts.append(f"/{db}")
            self.redis_url = "redis://" + "".join(redis_parts)
        
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self._redis: aioredis.Redis | None = None
        self.hit_count = 0
        self.miss_count = 0

    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection with connection pooling."""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
        return self._redis

    def _generate_key(self, messages: list[dict], **kwargs: dict) -> str:
        """Generate a unique cache key efficiently.

        Exclude provider, strategy, and model from cache key to enable cache hits
        across different providers and strategies after fallback scenarios.
        """
        cache_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k not in ["provider", "strategy", "model"]
        }

        raw = (
            json.dumps(messages, sort_keys=True)
            + "|"
            + json.dumps(cache_kwargs, sort_keys=True)
        )
        hash_key = hashlib.sha256(raw.encode()).hexdigest()
        return f"{self.key_prefix}{hash_key}"

    async def store(
        self,
        messages: list[dict],
        response: str,
        tokens: int,
        cost: float,
        ttl: float = 3600,
        **kwargs: dict[str, str | int | float | None],
    ) -> str:
        """Store a response in Redis cache with TTL.

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
        key = self._generate_key(messages, **kwargs)
        strategy = kwargs.get("strategy", "best")
        provider = kwargs.get("provider", "unknown")
        model = kwargs.get("model", "unknown")

        entry_data = {
            "response": response,
            "tokens": tokens,
            "cost": cost,
            "timestamp": time.time(),
            "ttl": ttl,
            "strategy": str(strategy),
            "provider": str(provider),
            "model": str(model),
        }

        try:
            redis = await self._get_redis()
            # Store as JSON string with TTL
            await redis.setex(
                key,
                int(ttl),
                json.dumps(entry_data),
            )
            logger.debug(f"Stored cache entry in Redis: {key[:16]}...")
        except Exception as e:
            logger.warning(f"Failed to store cache entry in Redis: {e}")

        return key

    async def retrieve(
        self, messages: list[dict], **kwargs: dict[str, str | int | float | None]
    ) -> CacheEntry | None:
        """Retrieve a cached response if available and not expired.

        Args:
            messages: The LLM messages to look up
            **kwargs: Additional metadata for cache key generation

        Returns:
            CacheEntry if found and valid, None otherwise
        """
        key = self._generate_key(messages, **kwargs)

        try:
            redis = await self._get_redis()
            data = await redis.get(key)

            if data is None:
                self.miss_count += 1
                logger.debug(f"Cache miss in Redis: {key[:16]}...")
                return None

            # Parse JSON data
            entry_data = json.loads(data)

            # Check if expired (TTL is handled by Redis, but double-check)
            timestamp = entry_data.get("timestamp", 0)
            ttl = entry_data.get("ttl", self.default_ttl)
            if time.time() > (timestamp + ttl):
                self.miss_count += 1
                logger.debug(f"Cache entry expired in Redis: {key[:16]}...")
                return None

            # Reconstruct CacheEntry
            entry = CacheEntry(
                response=entry_data["response"],
                tokens=entry_data["tokens"],
                cost=entry_data["cost"],
                timestamp=timestamp,
                ttl=ttl,
                strategy=entry_data.get("strategy", "best"),
                provider=entry_data.get("provider", "unknown"),
                model=entry_data.get("model", "unknown"),
            )

            self.hit_count += 1
            logger.debug(f"Cache hit in Redis: {key[:16]}...")
            return entry

        except Exception as e:
            logger.warning(f"Failed to retrieve cache entry from Redis: {e}")
            self.miss_count += 1
            return None

    async def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache metrics (entries, hits, misses, hit_rate, size_bytes)
        """
        try:
            redis = await self._get_redis()
            # Count keys with our prefix
            keys = await redis.keys(f"{self.key_prefix}*")
            entry_count = len(keys)

            # Estimate total size (sample-based for performance)
            total_size = 0
            sample_size = min(100, entry_count)
            if sample_size > 0:
                sample_keys = keys[:sample_size]
                for key in sample_keys:
                    data = await redis.get(key)
                    if data:
                        total_size += len(data)
                # Extrapolate to full size
                if sample_size < entry_count:
                    total_size = int(total_size * (entry_count / sample_size))

            hit_rate = (
                (self.hit_count / (self.hit_count + self.miss_count)) * 100
                if (self.hit_count + self.miss_count) > 0
                else 0
            )

            return {
                "entries": entry_count,
                "hit_count": self.hit_count,
                "miss_count": self.miss_count,
                "hit_rate": round(hit_rate, 2),
                "size_bytes": total_size,
            }
        except Exception as e:
            logger.warning(f"Failed to get Redis cache stats: {e}")
            return {
                "entries": 0,
                "hit_count": self.hit_count,
                "miss_count": self.miss_count,
                "hit_rate": 0.0,
                "size_bytes": 0,
            }

    async def clear(self) -> None:
        """Clear all cache entries with our prefix."""
        try:
            redis = await self._get_redis()
            keys = await redis.keys(f"{self.key_prefix}*")
            if keys:
                await redis.delete(*keys)
            self.hit_count = 0
            self.miss_count = 0
            logger.info(f"Cleared {len(keys)} entries from Redis cache")
        except Exception as e:
            logger.warning(f"Failed to clear Redis cache: {e}")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
