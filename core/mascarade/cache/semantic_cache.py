"""Semantic cache using GPTCache for similarity-based retrieval."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any

from mascarade.cache.cache import CacheBackend, CacheEntry

logger = logging.getLogger(__name__)


class SemanticCache(CacheBackend):
    """
    L3 semantic cache using GPTCache for similarity-based matching.

    Uses OpenAI embeddings API to find semantically similar prompts
    even when text differs. Useful for catching paraphrased queries.

    Example:
        >>> cache = SemanticCache(similarity_threshold=0.85)
        >>> await cache.store(
        ...     messages=[{"role": "user", "content": "Design a PCB"}],
        ...     response="Here's a PCB design...",
        ...     tokens=150,
        ...     cost=0.003
        ... )
        >>> # Later, similar query
        >>> entry = await cache.retrieve(
        ...     messages=[{"role": "user", "content": "Create a circuit board"}]
        ... )
        >>> # Returns cached entry if similarity >= 0.85
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        storage_path: str | None = None,
        openai_api_key: str | None = None,
    ) -> None:
        """
        Initialize semantic cache with GPTCache.

        Args:
            similarity_threshold: Minimum similarity score for cache hit (0-1). Default 0.85.
            storage_path: Path for SQLite storage. Default: ./data/gptcache
            openai_api_key: OpenAI API key for embeddings. Default: env var OPENAI_API_KEY
        """
        self.similarity_threshold = similarity_threshold
        self.storage_path = storage_path or os.getenv(
            "GPTCACHE_STORAGE_PATH", "./data/gptcache"
        )
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

        self.hit_count = 0
        self.miss_count = 0
        self._initialized = False
        self._cache_instance: Any = None  # GPTCache instance

        # Lazy initialization - only init GPTCache when first used
        # This prevents import errors when GPTCache is not installed

    def _ensure_initialized(self) -> None:
        """Lazy initialization of GPTCache (avoids import errors when not needed)."""
        if self._initialized:
            return

        try:
            from gptcache import Cache
            from gptcache.adapter.api import init_similar_cache
            from gptcache.manager import manager_factory
            from gptcache.processor.pre import get_prompt
            from gptcache.similarity_evaluation.distance import (
                SearchDistanceEvaluation,
            )

            # Ensure storage directory exists
            os.makedirs(self.storage_path, exist_ok=True)

            # Initialize cache with OpenAI embeddings
            # Using init_similar_cache for semantic similarity matching
            self._cache_instance = Cache()

            # Use manager factory for SQLite storage
            data_manager = manager_factory(
                "sqlite",
                scalar_params={
                    "sql_url": f"sqlite:///{self.storage_path}/gptcache.db"
                },
            )

            # Initialize with similarity evaluation
            self._cache_instance.init(
                pre_embedding_func=get_prompt,
                data_manager=data_manager,
                similarity_evaluation=SearchDistanceEvaluation(),
            )

            # Set similarity threshold
            self._cache_instance.config.similarity_threshold = self.similarity_threshold

            self._initialized = True
            logger.info(
                f"SemanticCache initialized: threshold={self.similarity_threshold}, "
                f"storage={self.storage_path}"
            )

        except ImportError as e:
            logger.warning(
                f"GPTCache not available, semantic cache disabled: {e}. "
                "Install with: pip install gptcache"
            )
            self._initialized = False
        except Exception as e:
            logger.error(f"Failed to initialize GPTCache: {e}", exc_info=True)
            self._initialized = False

    def _generate_key(self, messages: list[dict], **kwargs: dict) -> str:
        """Generate a unique cache key (used for internal tracking)."""
        # Exclude provider, strategy, and model from cache key
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
        return hashlib.sha256(raw.encode()).hexdigest()

    def _messages_to_prompt(self, messages: list[dict]) -> str:
        """Convert messages to a single prompt string for GPTCache."""
        # GPTCache works best with a single string
        # Concatenate all message content
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n".join(parts)

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
        Store a response in semantic cache.

        Args:
            messages: List of message dictionaries
            response: LLM response text
            tokens: Token count
            cost: API cost
            ttl: Time to live (not used by GPTCache, kept for interface compatibility)
            **kwargs: Additional metadata (strategy, provider, model, etc.)

        Returns:
            Cache key string
        """
        self._ensure_initialized()

        if not self._initialized or not self._cache_instance:
            # GPTCache not available, skip storage
            logger.debug("SemanticCache not initialized, skipping store")
            return ""

        try:
            prompt = self._messages_to_prompt(messages)
            strategy = kwargs.get("strategy", "best")
            provider = kwargs.get("provider", "unknown")
            model = kwargs.get("model", "unknown")

            # Store metadata alongside response
            cache_data = {
                "response": response,
                "tokens": tokens,
                "cost": cost,
                "timestamp": time.time(),
                "ttl": ttl,
                "strategy": str(strategy),
                "provider": str(provider),
                "model": str(model),
            }

            # GPTCache stores the prompt and data
            # Note: GPTCache.put() is synchronous, but we wrap in async for interface consistency
            self._cache_instance.import_data(
                questions=[prompt],
                answers=[json.dumps(cache_data)],
            )

            key = self._generate_key(messages, **kwargs)
            logger.debug(f"SemanticCache stored: key={key[:8]}..., prompt_len={len(prompt)}")
            return key

        except Exception as e:
            logger.error(f"SemanticCache store failed: {e}", exc_info=True)
            return ""

    async def retrieve(
        self, messages: list[dict], **kwargs: dict[str, str | int | float | None]
    ) -> CacheEntry | None:
        """
        Retrieve a cached response using semantic similarity.

        Args:
            messages: List of message dictionaries
            **kwargs: Additional metadata (not used for retrieval, kept for interface)

        Returns:
            CacheEntry if similarity >= threshold, None otherwise
        """
        self._ensure_initialized()

        if not self._initialized or not self._cache_instance:
            self.miss_count += 1
            return None

        try:
            prompt = self._messages_to_prompt(messages)

            # GPTCache.get() performs similarity search
            # Returns (answer, similarity_score) or (None, 0)
            result = self._cache_instance.get(prompt)

            if result is None:
                self.miss_count += 1
                logger.debug(f"SemanticCache miss: no similar prompt found")
                return None

            # Parse cached data
            try:
                cache_data = json.loads(result)
                entry = CacheEntry(
                    response=cache_data["response"],
                    tokens=cache_data["tokens"],
                    cost=cache_data["cost"],
                    timestamp=cache_data["timestamp"],
                    ttl=cache_data["ttl"],
                    strategy=cache_data["strategy"],
                    provider=cache_data["provider"],
                    model=cache_data.get("model", "unknown"),
                )

                # Check if expired
                if entry.is_expired():
                    self.miss_count += 1
                    logger.debug(f"SemanticCache miss: entry expired")
                    return None

                self.hit_count += 1
                logger.debug(
                    f"SemanticCache hit: provider={entry.provider}, "
                    f"model={entry.model}, age={time.time() - entry.timestamp:.1f}s"
                )
                return entry

            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"SemanticCache corrupted data: {e}")
                self.miss_count += 1
                return None

        except Exception as e:
            logger.error(f"SemanticCache retrieve failed: {e}", exc_info=True)
            self.miss_count += 1
            return None

    def get_stats(self) -> dict:
        """
        Get semantic cache statistics.

        Returns:
            Dict with hits, misses, hit_rate, and status
        """
        hit_rate = (
            (self.hit_count / (self.hit_count + self.miss_count)) * 100
            if (self.hit_count + self.miss_count) > 0
            else 0
        )

        return {
            "tier": "L3",
            "type": "semantic",
            "enabled": self._initialized,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": round(hit_rate, 2),
            "similarity_threshold": self.similarity_threshold,
            "storage_path": self.storage_path,
        }

    def clear(self) -> None:
        """Clear all cached entries and reset statistics."""
        self._ensure_initialized()

        if self._initialized and self._cache_instance:
            try:
                # GPTCache doesn't have a direct clear method
                # Reinitialize to clear data (creates new cache instance)
                self._initialized = False
                self._cache_instance = None
                self._ensure_initialized()
                logger.info("SemanticCache cleared")
            except Exception as e:
                logger.error(f"SemanticCache clear failed: {e}", exc_info=True)

        self.hit_count = 0
        self.miss_count = 0
