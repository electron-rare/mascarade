"""Tests for multi-tier cache orchestrator."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from mascarade.cache.cache import CacheEntry, InMemoryCache
from mascarade.cache.multi_tier_cache import MultiTierCache


class MockAsyncCache:
    """Mock async cache backend for testing."""

    def __init__(self, name="MockCache"):
        self.name = name
        self.storage = {}
        self.hit_count = 0
        self.miss_count = 0
        self.store_called = 0
        self.retrieve_called = 0
        self.should_fail = False

    async def store(self, messages, response, tokens, cost, ttl=3600, **kwargs):
        """Store entry in mock cache."""
        if self.should_fail:
            raise ConnectionError(f"{self.name} unavailable")

        self.store_called += 1
        key = str(hash(str(messages)))
        self.storage[key] = CacheEntry(
            response=response,
            tokens=tokens,
            cost=cost,
            timestamp=time.time(),
            ttl=ttl,
            strategy=kwargs.get("strategy", "best"),
            provider=kwargs.get("provider", "unknown"),
            model=kwargs.get("model", "unknown"),
        )
        return key

    async def retrieve(self, messages, **kwargs):
        """Retrieve entry from mock cache."""
        if self.should_fail:
            raise ConnectionError(f"{self.name} unavailable")

        self.retrieve_called += 1
        key = str(hash(str(messages)))
        entry = self.storage.get(key)

        if entry and not entry.is_expired():
            self.hit_count += 1
            return entry

        self.miss_count += 1
        return None

    async def get_stats(self):
        """Get cache statistics."""
        if self.should_fail:
            raise ConnectionError(f"{self.name} unavailable")

        hit_rate = (
            (self.hit_count / (self.hit_count + self.miss_count)) * 100
            if (self.hit_count + self.miss_count) > 0
            else 0
        )
        return {
            "entries": len(self.storage),
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": round(hit_rate, 2),
            "size_bytes": 0,
        }

    async def clear(self):
        """Clear all entries."""
        if self.should_fail:
            raise ConnectionError(f"{self.name} unavailable")

        self.storage.clear()
        self.hit_count = 0
        self.miss_count = 0

    async def close(self):
        """Close connection."""
        pass


class MockSyncCache:
    """Mock sync cache backend for L3 (SemanticCache-like)."""

    def __init__(self, name="MockSyncCache"):
        self.name = name
        self.storage = {}
        self.hit_count = 0
        self.miss_count = 0
        self.should_fail = False

    async def store(self, messages, response, tokens, cost, ttl=3600, **kwargs):
        """Store entry in mock cache."""
        if self.should_fail:
            raise ConnectionError(f"{self.name} unavailable")

        key = str(hash(str(messages)))
        self.storage[key] = CacheEntry(
            response=response,
            tokens=tokens,
            cost=cost,
            timestamp=time.time(),
            ttl=ttl,
            strategy=kwargs.get("strategy", "best"),
            provider=kwargs.get("provider", "unknown"),
            model=kwargs.get("model", "unknown"),
        )
        return key

    async def retrieve(self, messages, **kwargs):
        """Retrieve entry from mock cache."""
        if self.should_fail:
            raise ConnectionError(f"{self.name} unavailable")

        key = str(hash(str(messages)))
        entry = self.storage.get(key)

        if entry and not entry.is_expired():
            self.hit_count += 1
            return entry

        self.miss_count += 1
        return None

    async def get_stats(self):
        """Get cache statistics."""
        if self.should_fail:
            raise ConnectionError(f"{self.name} unavailable")

        hit_rate = (
            (self.hit_count / (self.hit_count + self.miss_count)) * 100
            if (self.hit_count + self.miss_count) > 0
            else 0
        )
        return {
            "entries": len(self.storage),
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": round(hit_rate, 2),
            "size_bytes": 0,
        }

    async def clear(self):
        """Clear all entries."""
        if self.should_fail:
            raise ConnectionError(f"{self.name} unavailable")

        self.storage.clear()
        self.hit_count = 0
        self.miss_count = 0


def test_multi_tier_cache_initialization():
    """MultiTierCache initializes with correct defaults."""
    cache = MultiTierCache()

    assert cache.l1 is not None
    assert isinstance(cache.l1, InMemoryCache)
    assert cache.l2 is None
    assert cache.l3 is None
    assert cache.l2_available is False
    assert cache.l3_available is False


def test_multi_tier_cache_with_all_tiers():
    """MultiTierCache initializes with all tiers enabled."""
    l1 = InMemoryCache(max_size=500)
    l2 = MockAsyncCache("L2")
    l3 = MockSyncCache("L3")

    cache = MultiTierCache(l1=l1, l2=l2, l3=l3)

    assert cache.l1 is l1
    assert cache.l2 is l2
    assert cache.l3 is l3
    assert cache.l2_available is True
    assert cache.l3_available is True


def test_tiers_property():
    """MultiTierCache tiers property returns all tiers."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")

    cache = MultiTierCache(l1=l1, l2=l2)
    tiers = cache.tiers

    assert tiers["L1"] is l1
    assert tiers["L2"] is l2
    assert tiers["L3"] is None


@pytest.mark.asyncio
async def test_store_l1_only():
    """MultiTierCache stores in L1 when only L1 available."""
    cache = MultiTierCache()
    messages = [{"role": "user", "content": "test"}]

    key = await cache.store(messages=messages, response="test response", tokens=10, cost=0.001)

    assert key is not None
    # Verify stored in L1
    entry = cache.l1.retrieve(messages)
    assert entry is not None
    assert entry.response == "test response"


@pytest.mark.asyncio
async def test_store_all_tiers():
    """MultiTierCache stores in all available tiers."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")
    l3 = MockSyncCache("L3")

    cache = MultiTierCache(l1=l1, l2=l2, l3=l3)
    messages = [{"role": "user", "content": "test"}]

    key = await cache.store(messages=messages, response="test response", tokens=10, cost=0.001)

    assert key is not None

    # Verify stored in all tiers
    assert l1.retrieve(messages) is not None
    assert l2.store_called == 1
    assert l3.storage  # Has data


@pytest.mark.asyncio
async def test_retrieve_l1_hit():
    """MultiTierCache returns immediately on L1 hit."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")

    cache = MultiTierCache(l1=l1, l2=l2)
    messages = [{"role": "user", "content": "test"}]

    # Store in L1
    l1.store(messages, "l1 response", 10, 0.001)

    # Retrieve should hit L1
    entry = await cache.retrieve(messages)

    assert entry is not None
    assert entry.response == "l1 response"
    assert l2.retrieve_called == 0  # L2 should not be called


@pytest.mark.asyncio
async def test_retrieve_l2_hit_backfills_l1():
    """MultiTierCache backfills L1 on L2 hit."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")

    cache = MultiTierCache(l1=l1, l2=l2)
    messages = [{"role": "user", "content": "test"}]

    # Store only in L2
    await l2.store(messages, "l2 response", 10, 0.001)

    # Retrieve should hit L2 and backfill L1
    entry = await cache.retrieve(messages)

    assert entry is not None
    assert entry.response == "l2 response"
    assert l2.retrieve_called == 1

    # Verify L1 was backfilled
    l1_entry = l1.retrieve(messages)
    assert l1_entry is not None
    assert l1_entry.response == "l2 response"


@pytest.mark.asyncio
async def test_retrieve_l3_hit_backfills_l1_and_l2():
    """MultiTierCache backfills L1 and L2 on L3 hit."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")
    l3 = MockSyncCache("L3")

    cache = MultiTierCache(l1=l1, l2=l2, l3=l3)
    messages = [{"role": "user", "content": "test"}]

    # Store only in L3
    await l3.store(messages, "l3 response", 10, 0.001)

    # Retrieve should hit L3 and backfill L1 and L2
    entry = await cache.retrieve(messages)

    assert entry is not None
    assert entry.response == "l3 response"

    # Verify L1 was backfilled
    l1_entry = l1.retrieve(messages)
    assert l1_entry is not None
    assert l1_entry.response == "l3 response"

    # Verify L2 was backfilled
    l2_entry = await l2.retrieve(messages)
    assert l2_entry is not None
    assert l2_entry.response == "l3 response"


@pytest.mark.asyncio
async def test_retrieve_miss_all_tiers():
    """MultiTierCache returns None on miss in all tiers."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")
    l3 = MockSyncCache("L3")

    cache = MultiTierCache(l1=l1, l2=l2, l3=l3)
    messages = [{"role": "user", "content": "not cached"}]

    entry = await cache.retrieve(messages)

    assert entry is None
    assert l2.retrieve_called == 1


@pytest.mark.asyncio
async def test_l2_failure_degrades_gracefully():
    """MultiTierCache degrades to L1 when L2 fails."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")
    l2.should_fail = True

    cache = MultiTierCache(l1=l1, l2=l2)
    messages = [{"role": "user", "content": "test"}]

    # Store should succeed (L1 works)
    key = await cache.store(messages, "test response", 10, 0.001)
    assert key is not None

    # L2 should be marked as unavailable
    assert cache.l2_available is False


@pytest.mark.asyncio
async def test_l2_retrieve_failure_degrades():
    """MultiTierCache marks L2 unavailable on retrieve failure."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")

    cache = MultiTierCache(l1=l1, l2=l2)
    messages = [{"role": "user", "content": "test"}]

    # Make L2 fail on retrieve
    l2.should_fail = True

    # Retrieve should not crash
    entry = await cache.retrieve(messages)
    assert entry is None

    # L2 should be marked unavailable
    assert cache.l2_available is False


@pytest.mark.asyncio
async def test_l3_failure_does_not_disable_tier():
    """MultiTierCache continues trying L3 even after failures."""
    l1 = InMemoryCache()
    l3 = MockSyncCache("L3")

    cache = MultiTierCache(l1=l1, l3=l3)
    messages = [{"role": "user", "content": "test"}]

    # Make L3 fail
    l3.should_fail = True

    # Store should still succeed in L1
    key = await cache.store(messages, "test response", 10, 0.001)
    assert key is not None

    # L3 should still be marked as available (failures are expected)
    assert cache.l3_available is True


@pytest.mark.asyncio
async def test_get_stats_aggregates_all_tiers():
    """MultiTierCache aggregates stats from all tiers."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")
    l3 = MockSyncCache("L3")

    cache = MultiTierCache(l1=l1, l2=l2, l3=l3)

    # Simulate some activity
    l1.hit_count = 10
    l1.miss_count = 5
    l2.hit_count = 8
    l2.miss_count = 7
    l3.hit_count = 2
    l3.miss_count = 3

    stats = await cache.get_stats()

    assert "tiers" in stats
    assert "L1" in stats["tiers"]
    assert "L2" in stats["tiers"]
    assert "L3" in stats["tiers"]

    assert "overall" in stats
    assert stats["overall"]["total_hits"] == 20  # 10 + 8 + 2
    assert stats["overall"]["total_misses"] == 15  # 5 + 7 + 3
    assert stats["overall"]["combined_hit_rate"] == 57.14  # 20/(20+15) * 100

    assert "available_tiers" in stats
    assert "L1" in stats["available_tiers"]
    assert "L2" in stats["available_tiers"]
    assert "L3" in stats["available_tiers"]

    assert stats["degraded"] is False


@pytest.mark.asyncio
async def test_get_stats_degraded_when_l2_unavailable():
    """MultiTierCache reports degraded status when L2 unavailable."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")

    cache = MultiTierCache(l1=l1, l2=l2)

    # Mark L2 as unavailable
    cache.l2_available = False

    stats = await cache.get_stats()

    assert stats["degraded"] is True
    assert "L1" in stats["available_tiers"]
    assert "L2" not in stats["available_tiers"]


@pytest.mark.asyncio
async def test_get_stats_l1_only():
    """MultiTierCache stats work with L1 only."""
    cache = MultiTierCache()

    cache.l1.hit_count = 5
    cache.l1.miss_count = 3

    stats = await cache.get_stats()

    assert stats["overall"]["total_hits"] == 5
    assert stats["overall"]["total_misses"] == 3
    assert stats["degraded"] is True  # L2 disabled


@pytest.mark.asyncio
async def test_clear_all_tiers():
    """MultiTierCache clears all tiers."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")
    l3 = MockSyncCache("L3")

    cache = MultiTierCache(l1=l1, l2=l2, l3=l3)
    messages = [{"role": "user", "content": "test"}]

    # Store in all tiers
    await cache.store(messages, "test response", 10, 0.001)

    # Clear all
    await cache.clear()

    # Verify all cleared
    assert len(l1.cache) == 0
    assert len(l2.storage) == 0
    assert len(l3.storage) == 0
    assert l1.hit_count == 0
    assert l2.hit_count == 0
    assert l3.hit_count == 0


@pytest.mark.asyncio
async def test_clear_l1_failure_handled():
    """MultiTierCache handles L1 clear failures gracefully."""
    l1 = InMemoryCache()

    # Mock clear to raise exception
    def failing_clear():
        raise RuntimeError("Clear failed")

    l1.clear = failing_clear

    cache = MultiTierCache(l1=l1)

    # Should not raise
    await cache.clear()


@pytest.mark.asyncio
async def test_clear_l2_failure_handled():
    """MultiTierCache handles L2 clear failures gracefully."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")
    l2.should_fail = True

    cache = MultiTierCache(l1=l1, l2=l2)

    # Should not raise
    await cache.clear()


@pytest.mark.asyncio
async def test_close_connections():
    """MultiTierCache closes all connections."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")
    l3 = MockSyncCache("L3")

    l2.close = AsyncMock()
    l3.close = MagicMock()

    cache = MultiTierCache(l1=l1, l2=l2, l3=l3)

    await cache.close()

    l2.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_l2_failure_handled():
    """MultiTierCache handles L2 close failures gracefully."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")

    async def failing_close():
        raise RuntimeError("Close failed")

    l2.close = failing_close

    cache = MultiTierCache(l1=l1, l2=l2)

    # Should not raise
    await cache.close()


@pytest.mark.asyncio
async def test_concurrent_retrieve():
    """MultiTierCache handles concurrent retrieve operations."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")

    cache = MultiTierCache(l1=l1, l2=l2)
    messages = [{"role": "user", "content": "test"}]

    # Store in L2
    await l2.store(messages, "test response", 10, 0.001)

    # Concurrent retrieve operations
    tasks = [cache.retrieve(messages) for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # All should succeed
    assert all(r is not None for r in results)
    assert all(r.response == "test response" for r in results)


@pytest.mark.asyncio
async def test_backfill_l1_failure_handled():
    """MultiTierCache handles L1 backfill failures gracefully."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")

    cache = MultiTierCache(l1=l1, l2=l2)
    messages = [{"role": "user", "content": "test"}]

    # Store in L2
    await l2.store(messages, "test response", 10, 0.001)

    # Make L1 store fail
    def failing_store(*args, **kwargs):
        raise RuntimeError("L1 store failed")

    l1.store = failing_store

    # Retrieve should still succeed (L2 hit)
    entry = await cache.retrieve(messages)
    assert entry is not None
    assert entry.response == "test response"


@pytest.mark.asyncio
async def test_backfill_l2_failure_handled():
    """MultiTierCache handles L2 backfill failures gracefully."""
    l1 = InMemoryCache()
    l2 = MockAsyncCache("L2")
    l3 = MockSyncCache("L3")

    cache = MultiTierCache(l1=l1, l2=l2, l3=l3)
    messages = [{"role": "user", "content": "test"}]

    # Store in L3
    await l3.store(messages, "test response", 10, 0.001)

    # Make L2 backfill fail
    l2.should_fail = True

    # Retrieve should still succeed (L3 hit)
    entry = await cache.retrieve(messages)
    assert entry is not None
    assert entry.response == "test response"

    # L2 should be marked unavailable
    assert cache.l2_available is False
