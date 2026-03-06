"""Cache system for LLM responses."""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """Entrée de cache avec métadonnées."""

    response: str
    tokens: int
    cost: float
    timestamp: float
    ttl: float
    strategy: str
    provider: str
    model: str = "unknown"

    def is_expired(self) -> bool:
        """Vérifier si l'entrée de cache a expiré."""
        return time.time() > (self.timestamp + self.ttl)


class ResponseCache:
    """In-memory cache for LLM responses with LRU strategy."""

    def __init__(self, max_size: int = 1000) -> None:
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.max_size = max_size
        self.hit_count = 0
        self.miss_count = 0

    def _generate_key(self, messages: list[dict], **kwargs: dict) -> str:
        """Generate a unique cache key efficiently."""

        # Exclude provider, strategy, and model from cache key to enable cache hits across different providers
        # and strategies after fallback scenarios. Model is determined by provider selection.
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

    def store(
        self,
        messages: list[dict],
        response: str,
        tokens: int,
        cost: float,
        ttl: float = 3600,
        **kwargs: dict[str, str | int | float | None],
    ) -> str:
        """Store a response in cache with LRU strategy."""

        key = self._generate_key(messages, **kwargs)
        strategy = kwargs.get("strategy", "best")
        provider = kwargs.get("provider", "unknown")
        model = kwargs.get("model", "unknown")

        entry = CacheEntry(
            response=response,
            tokens=tokens,
            cost=cost,
            timestamp=time.time(),
            ttl=ttl,
            strategy=strategy,
            provider=provider,
            model=model,
        )

        # Move to end to mark as recently used (LRU)
        self.cache[key] = entry
        self.cache.move_to_end(key)

        # Appliquer la limite de taille
        if len(self.cache) > self.max_size:
            self._evict_oldest()

        return key

    def retrieve(
        self, messages: list[dict], **kwargs: dict[str, str | int | float | None]
    ) -> CacheEntry | None:
        """Retrieve a cached response if available (LRU)."""

        key = self._generate_key(messages, **kwargs)
        entry = self.cache.get(key)

        if entry and not entry.is_expired():
            self.hit_count += 1
            # Move to end to mark as recently used (LRU)
            self.cache.move_to_end(key)
            return entry

        self.miss_count += 1
        return None

    def _evict_oldest(self) -> None:
        """Supprimer l'entrée la plus ancienne (LRU) — O(1) via OrderedDict."""
        if self.cache:
            self.cache.popitem(last=False)

    def get_stats(self) -> dict:
        """Obtenir les statistiques du cache."""

        hit_rate = (
            (self.hit_count / (self.hit_count + self.miss_count)) * 100
            if (self.hit_count + self.miss_count) > 0
            else 0
        )

        return {
            "entries": len(self.cache),
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": round(hit_rate, 2),
            "size_bytes": sum(len(entry.response) for entry in self.cache.values()),
        }

    def clear(self) -> None:
        """Effacer toutes les entrées du cache."""
        self.cache.clear()
        self.hit_count = 0
        self.miss_count = 0
