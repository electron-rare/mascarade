"""Tests for Redis L2 cache implementation."""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from mascarade.cache.redis_cache import RedisCache


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock()
    redis_mock.keys = AsyncMock(return_value=[])
    redis_mock.delete = AsyncMock()
    redis_mock.close = AsyncMock()
    return redis_mock


@pytest.fixture
async def redis_cache(mock_redis):
    """Create a RedisCache instance with mocked Redis connection."""
    cache = RedisCache(redis_url="redis://localhost:6379/0")

    # Mock the _get_redis method to return our mock
    async def get_mock_redis():
        return mock_redis

    cache._get_redis = get_mock_redis
    cache._redis = mock_redis
    yield cache

    # Cleanup
    await cache.close()


def test_redis_cache_initialization():
    """RedisCache initializes with correct defaults."""
    cache = RedisCache()
    assert cache.redis_url == "redis://localhost:6379/0"
    assert cache.default_ttl == 3600
    assert cache.key_prefix == "mascarade:cache:"
    assert cache.hit_count == 0
    assert cache.miss_count == 0


def test_redis_cache_custom_config():
    """RedisCache accepts custom configuration."""
    cache = RedisCache(
        host="custom", port=6379, db=1, default_ttl=7200, key_prefix="test:cache:"
    )
    assert cache.default_ttl == 7200
    assert cache.key_prefix == "test:cache:"


def test_generate_key_consistency():
    """Cache keys are consistent for same messages."""
    cache = RedisCache()
    messages = [{"role": "user", "content": "hello"}]

    key1 = cache._generate_key(messages)
    key2 = cache._generate_key(messages)

    assert key1 == key2
    assert key1.startswith("mascarade:cache:")


def test_generate_key_excludes_provider_strategy():
    """Cache keys exclude provider, strategy, and model."""
    cache = RedisCache()
    messages = [{"role": "user", "content": "hello"}]

    key1 = cache._generate_key(
        messages, provider="openai", strategy="best", model="gpt-4"
    )
    key2 = cache._generate_key(
        messages, provider="anthropic", strategy="cheapest", model="claude-3"
    )

    # Keys should be identical since provider/strategy/model are excluded
    assert key1 == key2


def test_generate_key_different_for_different_messages():
    """Cache keys differ for different messages."""
    cache = RedisCache()
    messages1 = [{"role": "user", "content": "hello"}]
    messages2 = [{"role": "user", "content": "goodbye"}]

    key1 = cache._generate_key(messages1)
    key2 = cache._generate_key(messages2)

    assert key1 != key2


@pytest.mark.asyncio
async def test_store_success(redis_cache, mock_redis):
    """RedisCache stores entries successfully."""
    messages = [{"role": "user", "content": "test"}]
    response = "test response"

    key = await redis_cache.store(
        messages=messages,
        response=response,
        tokens=10,
        cost=0.001,
        ttl=3600,
        strategy="best",
        provider="openai",
        model="gpt-4",
    )

    assert key.startswith("mascarade:cache:")
    mock_redis.setex.assert_called_once()

    # Verify the call arguments
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == key  # Key
    assert call_args[0][1] == 3600  # TTL
    # Third argument is JSON data (verified by structure)


@pytest.mark.asyncio
async def test_store_failure_handled_gracefully(redis_cache, mock_redis):
    """RedisCache handles store failures gracefully."""
    mock_redis.setex.side_effect = ConnectionError("Redis unavailable")

    messages = [{"role": "user", "content": "test"}]

    # Should not raise, just log warning
    key = await redis_cache.store(
        messages=messages, response="test", tokens=10, cost=0.001
    )

    assert key.startswith("mascarade:cache:")


@pytest.mark.asyncio
async def test_retrieve_hit(redis_cache, mock_redis):
    """RedisCache retrieves cached entries successfully."""
    messages = [{"role": "user", "content": "test"}]

    # Mock Redis to return cached data
    cached_data = {
        "response": "cached response",
        "tokens": 10,
        "cost": 0.001,
        "timestamp": time.time(),
        "ttl": 3600,
        "strategy": "best",
        "provider": "openai",
        "model": "gpt-4",
    }

    import json

    mock_redis.get.return_value = json.dumps(cached_data)

    entry = await redis_cache.retrieve(messages)

    assert entry is not None
    assert entry.response == "cached response"
    assert entry.tokens == 10
    assert entry.cost == 0.001
    assert entry.strategy == "best"
    assert entry.provider == "openai"
    assert entry.model == "gpt-4"
    assert redis_cache.hit_count == 1
    assert redis_cache.miss_count == 0


@pytest.mark.asyncio
async def test_retrieve_miss(redis_cache, mock_redis):
    """RedisCache returns None on cache miss."""
    messages = [{"role": "user", "content": "test"}]

    mock_redis.get.return_value = None

    entry = await redis_cache.retrieve(messages)

    assert entry is None
    assert redis_cache.hit_count == 0
    assert redis_cache.miss_count == 1


@pytest.mark.asyncio
async def test_retrieve_expired_entry(redis_cache, mock_redis):
    """RedisCache returns None for expired entries."""
    messages = [{"role": "user", "content": "test"}]

    # Mock expired cache entry
    cached_data = {
        "response": "expired response",
        "tokens": 10,
        "cost": 0.001,
        "timestamp": time.time() - 7200,  # 2 hours ago
        "ttl": 3600,  # 1 hour TTL, so expired
        "strategy": "best",
        "provider": "openai",
        "model": "gpt-4",
    }

    import json

    mock_redis.get.return_value = json.dumps(cached_data)

    entry = await redis_cache.retrieve(messages)

    assert entry is None
    assert redis_cache.miss_count == 1


@pytest.mark.asyncio
async def test_retrieve_connection_failure(redis_cache, mock_redis):
    """RedisCache handles retrieve failures gracefully."""
    mock_redis.get.side_effect = ConnectionError("Redis unavailable")

    messages = [{"role": "user", "content": "test"}]

    # Should not raise, return None and increment miss count
    entry = await redis_cache.retrieve(messages)

    assert entry is None
    assert redis_cache.miss_count == 1


@pytest.mark.asyncio
async def test_get_stats(redis_cache, mock_redis):
    """RedisCache returns correct statistics."""
    # Mock Redis keys and data
    mock_redis.keys.return_value = [
        "mascarade:cache:key1",
        "mascarade:cache:key2",
        "mascarade:cache:key3",
    ]
    mock_redis.get.return_value = '{"response": "test", "tokens": 10}'

    # Simulate some hits and misses
    redis_cache.hit_count = 10
    redis_cache.miss_count = 5

    stats = await redis_cache.get_stats()

    assert stats["entries"] == 3
    assert stats["hit_count"] == 10
    assert stats["miss_count"] == 5
    assert stats["hit_rate"] == 66.67  # 10/(10+5) * 100
    assert "size_bytes" in stats


@pytest.mark.asyncio
async def test_get_stats_no_data(redis_cache, mock_redis):
    """RedisCache stats work with no data."""
    mock_redis.keys.return_value = []

    stats = await redis_cache.get_stats()

    assert stats["entries"] == 0
    assert stats["hit_count"] == 0
    assert stats["miss_count"] == 0
    assert stats["hit_rate"] == 0.0
    assert stats["size_bytes"] == 0


@pytest.mark.asyncio
async def test_get_stats_connection_failure(redis_cache, mock_redis):
    """RedisCache handles stats retrieval failures gracefully."""
    mock_redis.keys.side_effect = ConnectionError("Redis unavailable")

    stats = await redis_cache.get_stats()

    assert stats["entries"] == 0
    assert stats["hit_rate"] == 0.0


@pytest.mark.asyncio
async def test_clear(redis_cache, mock_redis):
    """RedisCache clears all entries successfully."""
    mock_redis.keys.return_value = ["mascarade:cache:key1", "mascarade:cache:key2"]

    redis_cache.hit_count = 10
    redis_cache.miss_count = 5

    await redis_cache.clear()

    mock_redis.delete.assert_called_once()
    assert redis_cache.hit_count == 0
    assert redis_cache.miss_count == 0


@pytest.mark.asyncio
async def test_clear_no_keys(redis_cache, mock_redis):
    """RedisCache handles clearing empty cache."""
    mock_redis.keys.return_value = []

    await redis_cache.clear()

    # Should not call delete if no keys
    mock_redis.delete.assert_not_called()


@pytest.mark.asyncio
async def test_clear_connection_failure(redis_cache, mock_redis):
    """RedisCache handles clear failures gracefully."""
    mock_redis.keys.side_effect = ConnectionError("Redis unavailable")

    # Should not raise, just log warning
    await redis_cache.clear()


@pytest.mark.asyncio
async def test_close_connection(redis_cache, mock_redis):
    """RedisCache closes connection properly."""
    await redis_cache.close()

    mock_redis.close.assert_called_once()
    assert redis_cache._redis is None


@pytest.mark.asyncio
async def test_close_when_not_connected():
    """RedisCache handles close when not connected."""
    cache = RedisCache()

    # Should not raise when closing without connection
    await cache.close()

    assert cache._redis is None


@pytest.mark.asyncio
async def test_hit_rate_calculation():
    """RedisCache calculates hit rate correctly."""
    cache = RedisCache()

    cache.hit_count = 75
    cache.miss_count = 25

    # Use mock to avoid actual Redis connection
    with patch.object(cache, "_get_redis") as mock_get_redis:
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])
        mock_get_redis.return_value = mock_redis

        stats = await cache.get_stats()

        assert stats["hit_rate"] == 75.0  # 75/(75+25) * 100


@pytest.mark.asyncio
async def test_concurrent_operations(redis_cache, mock_redis):
    """RedisCache handles concurrent operations correctly."""
    messages = [{"role": "user", "content": "test"}]

    # Simulate concurrent store operations
    tasks = [redis_cache.store(messages, f"response{i}", 10, 0.001) for i in range(10)]

    keys = await asyncio.gather(*tasks)

    # All keys should be the same (same messages)
    assert len(set(keys)) == 1
    assert mock_redis.setex.call_count == 10
