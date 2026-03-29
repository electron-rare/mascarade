"""Module de cache pour Mascarade."""

from .cache import AsyncCacheBackend, CacheBackend, CacheEntry, InMemoryCache
from .multi_tier_cache import MultiTierCache

# Backward compatibility alias
ResponseCache = InMemoryCache

__all__ = [
    "AsyncCacheBackend",
    "CacheBackend",
    "InMemoryCache",
    "ResponseCache",
    "CacheEntry",
    "MultiTierCache",
]
