"""Module de cache pour Mascarade."""

from .cache import CacheBackend, CacheEntry, InMemoryCache

# Backward compatibility alias
ResponseCache = InMemoryCache

__all__ = ["CacheBackend", "InMemoryCache", "ResponseCache", "CacheEntry"]
