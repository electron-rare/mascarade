"""Tests for usage tracking integration with router."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router
from mascarade.usage_tracking import (
    Usage,
    UsageStats,
    get_all_usage_stats,
    get_user_usage_stats,
    track_usage,
)


class MockProvider(LLMProvider):
    """Mock provider for testing."""

    def __init__(self):
        self.name = "mock"
        self.default_model = "mock-model"
        self.cost_per_million = (2.0, 4.0)
        self.speed_rank = 1
        self.quality_rank = 1

    async def send(self, messages, **kwargs):
        return LLMResponse(
            content="test response",
            model=self.default_model,
            provider=self.name,
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )

    async def stream(self, messages, **kwargs):
        yield "test"
        yield " response"

    def available_models(self):
        return [self.default_model]


def test_send_without_user_id():
    """Router.send() should work without user_id (backward compatible)."""
    r = Router()
    r._providers.clear()
    r.register(MockProvider())

    with patch("mascarade.router.router.track_usage") as mock_track:
        resp = asyncio.run(
            r.send(
                [{"role": "user", "content": "hello"}],
                strategy="specific",
                provider="mock",
            )
        )
        assert resp.content == "test response"
        assert resp.provider == "mock"
        # Should not call track_usage when user_id is not provided
        mock_track.assert_not_called()


def test_send_with_user_id():
    """Router.send() should track usage when user_id is provided."""
    r = Router()
    r._providers.clear()
    r.register(MockProvider())

    with patch("mascarade.router.router.track_usage") as mock_track:
        mock_track.return_value = asyncio.Future()
        mock_track.return_value.set_result(None)

        resp = asyncio.run(
            r.send(
                [{"role": "user", "content": "hello"}],
                strategy="specific",
                provider="mock",
                user_id=42,
            )
        )
        assert resp.content == "test response"
        assert resp.provider == "mock"

        # Should call track_usage with correct parameters
        mock_track.assert_called_once()
        call_args = mock_track.call_args
        assert call_args[1]["user_id"] == 42
        assert call_args[1]["provider"] == "mock"
        assert call_args[1]["model"] == "mock-model"
        assert call_args[1]["usage"]["input_tokens"] == 100
        assert call_args[1]["usage"]["output_tokens"] == 50
        assert call_args[1]["cost"] > 0


def test_stream_without_user_id():
    """Router.stream() should work without user_id (backward compatible)."""
    r = Router()
    r._providers.clear()
    r.register(MockProvider())

    with patch("mascarade.router.router.track_usage") as mock_track:
        tokens = []

        async def collect():
            async for token in r.stream(
                [{"role": "user", "content": "hello"}],
                strategy="specific",
                provider="mock",
            ):
                tokens.append(token)

        asyncio.run(collect())
        assert "".join(tokens) == "test response"
        # Should not call track_usage when user_id is not provided
        mock_track.assert_not_called()


def test_stream_with_user_id():
    """Router.stream() should track usage when user_id is provided."""
    r = Router()
    r._providers.clear()
    r.register(MockProvider())

    with patch("mascarade.router.router.track_usage") as mock_track:
        mock_track.return_value = asyncio.Future()
        mock_track.return_value.set_result(None)

        tokens = []

        async def collect():
            async for token in r.stream(
                [{"role": "user", "content": "hello"}],
                strategy="specific",
                provider="mock",
                user_id=42,
            ):
                tokens.append(token)

        asyncio.run(collect())
        assert "".join(tokens) == "test response"

        # Should call track_usage with correct parameters
        # Note: streaming doesn't have token counts, so tokens=0
        mock_track.assert_called_once()
        call_args = mock_track.call_args
        assert call_args[1]["user_id"] == 42
        assert call_args[1]["provider"] == "mock"
        assert call_args[1]["model"] == "mock-model"
        assert call_args[1]["cost"] == 0.0


def test_send_failure_does_not_track():
    """Router.send() should not track usage on provider failure."""

    class FailProvider(LLMProvider):
        name = "fail"
        default_model = "fail-model"
        cost_per_million = (1.0, 1.0)
        speed_rank = 1
        quality_rank = 1

        async def send(self, messages, **kwargs):
            raise ConnectionError("forced failure")

        async def stream(self, messages, **kwargs):
            raise ConnectionError("forced failure")
            yield  # pragma: no cover

        def available_models(self):
            return [self.default_model]

    r = Router()
    r._providers.clear()
    r.register(FailProvider())

    with patch("mascarade.router.router.track_usage") as mock_track:
        try:
            asyncio.run(
                r.send(
                    [{"role": "user", "content": "hello"}],
                    strategy="specific",
                    provider="fail",
                    user_id=42,
                )
            )
            assert False, "Should have raised RuntimeError"
        except RuntimeError:
            pass

        # Should not track usage when all attempts fail
        mock_track.assert_not_called()


def test_send_tracks_actual_provider_used():
    """Router.send() should track the actual provider used, not requested."""

    class Provider1(LLMProvider):
        name = "provider1"
        default_model = "model1"
        cost_per_million = (10.0, 20.0)
        speed_rank = 2
        quality_rank = 3

        async def send(self, messages, **kwargs):
            raise ConnectionError("fail")

        async def stream(self, messages, **kwargs):
            yield "x"

        def available_models(self):
            return [self.default_model]

    class Provider2(LLMProvider):
        name = "provider2"
        default_model = "model2"
        cost_per_million = (5.0, 10.0)
        speed_rank = 1
        quality_rank = 2

        async def send(self, messages, **kwargs):
            return LLMResponse(
                content="fallback success",
                model=self.default_model,
                provider=self.name,
                usage={"input_tokens": 10, "output_tokens": 20},
            )

        async def stream(self, messages, **kwargs):
            yield "y"

        def available_models(self):
            return [self.default_model]

    r = Router()
    r._providers.clear()
    r.register(Provider1())
    r.register(Provider2())

    with patch("mascarade.router.router.track_usage") as mock_track:
        mock_track.return_value = asyncio.Future()
        mock_track.return_value.set_result(None)

        resp = asyncio.run(
            r.send(
                [{"role": "user", "content": "hello"}],
                strategy="best",
                user_id=42,
            )
        )

        # First provider failed, should have fallen back to provider2
        assert resp.provider == "provider2"

        # Should track usage for provider2, not provider1
        mock_track.assert_called_once()
        call_args = mock_track.call_args
        assert call_args[1]["provider"] == "provider2"
        assert call_args[1]["model"] == "model2"


# --- Unit Tests for Usage Tracking Functions ---


@pytest.mark.asyncio
async def test_track_usage_without_db_pool():
    """track_usage should skip silently when database pool is not initialized."""
    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        mock_get_pool.return_value = None

        # Should not raise even without database
        await track_usage(
            user_id=1,
            provider="test-provider",
            model="test-model",
            usage={"input_tokens": 100, "output_tokens": 50},
            cost=0.01,
        )


@pytest.mark.asyncio
async def test_track_usage_with_db_pool():
    """track_usage should insert usage record when database pool exists."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock()

    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        mock_get_pool.return_value = mock_pool

        await track_usage(
            user_id=42,
            provider="claude",
            model="claude-3-5-sonnet-20241022",
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            cost=0.0123,
        )

        # Verify insert was called with correct parameters
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert "INSERT INTO usage_records" in call_args[0]
        assert call_args[1] == 42  # user_id
        assert call_args[2] == "claude"  # provider
        assert call_args[3] == "claude-3-5-sonnet-20241022"  # model
        assert call_args[4] == 100  # input_tokens
        assert call_args[5] == 50  # output_tokens
        assert call_args[6] == 150  # total_tokens
        assert call_args[7] == 0.0123  # cost


@pytest.mark.asyncio
async def test_track_usage_calculates_total_tokens():
    """track_usage should calculate total_tokens if not provided."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock()

    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        mock_get_pool.return_value = mock_pool

        # Provide usage without total_tokens
        await track_usage(
            user_id=42,
            provider="test",
            model="test-model",
            usage={"input_tokens": 100, "output_tokens": 50},
            cost=0.01,
        )

        call_args = mock_conn.execute.call_args[0]
        # total_tokens should be calculated as 100 + 50 = 150
        assert call_args[6] == 150


@pytest.mark.asyncio
async def test_track_usage_handles_db_error():
    """track_usage should not raise when database error occurs."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(side_effect=Exception("Database error"))

    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        mock_get_pool.return_value = mock_pool

        # Should not raise even when database errors occur
        await track_usage(
            user_id=1,
            provider="test",
            model="test-model",
            usage={"input_tokens": 100, "output_tokens": 50},
            cost=0.01,
        )


@pytest.mark.asyncio
async def test_get_user_usage_stats_no_db_pool():
    """get_user_usage_stats should raise when database pool is not initialized."""
    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        mock_get_pool.return_value = None

        with pytest.raises(RuntimeError, match="Database pool not initialized"):
            await get_user_usage_stats(user_id=1)


@pytest.mark.asyncio
async def test_get_user_usage_stats_basic():
    """get_user_usage_stats should return aggregated statistics."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    # Mock the main stats query
    mock_conn.fetchrow = AsyncMock(
        return_value={
            "total_requests": 10,
            "total_tokens": 5000,
            "total_input_tokens": 3000,
            "total_output_tokens": 2000,
            "total_cost": 0.123,
        }
    )

    # Mock the provider breakdown query
    provider_rows = [
        {"provider": "claude", "count": 6},
        {"provider": "openai", "count": 4},
    ]

    # Mock the model breakdown query
    model_rows = [
        {"model": "claude-3-5-sonnet-20241022", "count": 6},
        {"model": "gpt-4o", "count": 4},
    ]

    # Create a side effect function that returns different values for different queries
    async def fetch_side_effect(query, *args):
        if "GROUP BY provider" in query:
            return provider_rows
        elif "GROUP BY model" in query:
            return model_rows
        return []

    mock_conn.fetch = AsyncMock(side_effect=fetch_side_effect)

    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        mock_get_pool.return_value = mock_pool

        stats = await get_user_usage_stats(user_id=42)

        assert stats.user_id == 42
        assert stats.total_requests == 10
        assert stats.total_tokens == 5000
        assert stats.total_input_tokens == 3000
        assert stats.total_output_tokens == 2000
        assert stats.total_cost == 0.123
        assert stats.providers == {"claude": 6, "openai": 4}
        assert stats.models == {"claude-3-5-sonnet-20241022": 6, "gpt-4o": 4}


@pytest.mark.asyncio
async def test_get_user_usage_stats_with_date_filters():
    """get_user_usage_stats should apply date filters correctly."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    mock_conn.fetchrow = AsyncMock(
        return_value={
            "total_requests": 5,
            "total_tokens": 2500,
            "total_input_tokens": 1500,
            "total_output_tokens": 1000,
            "total_cost": 0.05,
        }
    )

    mock_conn.fetch = AsyncMock(return_value=[])

    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        mock_get_pool.return_value = mock_pool

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        stats = await get_user_usage_stats(
            user_id=42, start_date=start_date, end_date=end_date
        )

        # Verify the query was called with date parameters
        call_args = mock_conn.fetchrow.call_args[0]
        assert "created_at >= $2" in call_args[0]
        assert "created_at <= $3" in call_args[0]
        assert call_args[1] == 42
        assert call_args[2] == start_date
        assert call_args[3] == end_date


@pytest.mark.asyncio
async def test_get_user_usage_stats_empty_results():
    """get_user_usage_stats should handle empty results correctly."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    # Mock empty results
    mock_conn.fetchrow = AsyncMock(
        return_value={
            "total_requests": None,
            "total_tokens": None,
            "total_input_tokens": None,
            "total_output_tokens": None,
            "total_cost": None,
        }
    )

    mock_conn.fetch = AsyncMock(return_value=[])

    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        mock_get_pool.return_value = mock_pool

        stats = await get_user_usage_stats(user_id=999)

        # Should return zeros for empty results
        assert stats.user_id == 999
        assert stats.total_requests == 0
        assert stats.total_tokens == 0
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.total_cost == 0.0
        assert stats.providers == {}
        assert stats.models == {}


@pytest.mark.asyncio
async def test_get_all_usage_stats_no_db_pool():
    """get_all_usage_stats should raise when database pool is not initialized."""
    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        mock_get_pool.return_value = None

        with pytest.raises(RuntimeError, match="Database pool not initialized"):
            await get_all_usage_stats()


@pytest.mark.asyncio
async def test_get_all_usage_stats_basic():
    """get_all_usage_stats should return statistics for all users."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    # Mock distinct user IDs query
    mock_conn.fetch = AsyncMock(
        return_value=[
            {"user_id": 1},
            {"user_id": 2},
            {"user_id": 3},
        ]
    )

    # Mock get_user_usage_stats calls
    mock_stats = [
        UsageStats(
            user_id=1,
            total_requests=5,
            total_tokens=1000,
            total_input_tokens=600,
            total_output_tokens=400,
            total_cost=0.05,
            providers={"claude": 5},
            models={"claude-3-5-sonnet-20241022": 5},
        ),
        UsageStats(
            user_id=2,
            total_requests=10,
            total_tokens=2000,
            total_input_tokens=1200,
            total_output_tokens=800,
            total_cost=0.10,
            providers={"openai": 10},
            models={"gpt-4o": 10},
        ),
        UsageStats(
            user_id=3,
            total_requests=3,
            total_tokens=500,
            total_input_tokens=300,
            total_output_tokens=200,
            total_cost=0.03,
            providers={"claude": 3},
            models={"claude-3-5-sonnet-20241022": 3},
        ),
    ]

    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        with patch("mascarade.usage_tracking.get_user_usage_stats") as mock_get_user:
            mock_get_pool.return_value = mock_pool
            mock_get_user.side_effect = mock_stats

            stats = await get_all_usage_stats()

            assert len(stats) == 3
            assert stats[0].user_id == 1
            assert stats[1].user_id == 2
            assert stats[2].user_id == 3


@pytest.mark.asyncio
async def test_get_all_usage_stats_with_date_filters():
    """get_all_usage_stats should pass date filters to get_user_usage_stats."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    mock_conn.fetch = AsyncMock(
        return_value=[
            {"user_id": 1},
            {"user_id": 2},
        ]
    )

    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)

    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        with patch("mascarade.usage_tracking.get_user_usage_stats") as mock_get_user:
            mock_get_pool.return_value = mock_pool
            mock_get_user.return_value = UsageStats(
                user_id=1,
                total_requests=0,
                total_tokens=0,
                total_input_tokens=0,
                total_output_tokens=0,
                total_cost=0.0,
                providers={},
                models={},
            )

            await get_all_usage_stats(start_date=start_date, end_date=end_date)

            # Verify date filters were passed to fetchrow query
            call_args = mock_conn.fetch.call_args[0]
            assert "created_at >= $1" in call_args[0]
            assert "created_at <= $2" in call_args[0]

            # Verify date filters were passed to get_user_usage_stats
            assert mock_get_user.call_count == 2
            for call in mock_get_user.call_args_list:
                assert call[0][1] == start_date  # start_date
                assert call[0][2] == end_date  # end_date


@pytest.mark.asyncio
async def test_get_all_usage_stats_no_users():
    """get_all_usage_stats should return empty list when no users have usage."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    # Mock no users found
    mock_conn.fetch = AsyncMock(return_value=[])

    with patch("mascarade.usage_tracking.get_db_pool") as mock_get_pool:
        mock_get_pool.return_value = mock_pool

        stats = await get_all_usage_stats()

        assert stats == []


def test_usage_from_record():
    """Usage.from_record should correctly convert database record to Usage model."""
    record = {
        "id": 123,
        "user_id": 42,
        "provider": "claude",
        "model": "claude-3-5-sonnet-20241022",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "cost": 0.0123,
        "created_at": datetime(2024, 1, 1, 12, 0, 0),
    }

    usage = Usage.from_record(record)

    assert usage.id == 123
    assert usage.user_id == 42
    assert usage.provider == "claude"
    assert usage.model == "claude-3-5-sonnet-20241022"
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.total_tokens == 150
    assert usage.cost == 0.0123
    assert usage.created_at == datetime(2024, 1, 1, 12, 0, 0)


def test_usage_stats_model():
    """UsageStats model should correctly hold aggregated statistics."""
    stats = UsageStats(
        user_id=42,
        total_requests=100,
        total_tokens=50000,
        total_input_tokens=30000,
        total_output_tokens=20000,
        total_cost=1.23,
        providers={"claude": 60, "openai": 40},
        models={"claude-3-5-sonnet-20241022": 60, "gpt-4o": 40},
    )

    assert stats.user_id == 42
    assert stats.total_requests == 100
    assert stats.total_tokens == 50000
    assert stats.total_input_tokens == 30000
    assert stats.total_output_tokens == 20000
    assert stats.total_cost == 1.23
    assert stats.providers == {"claude": 60, "openai": 40}
    assert stats.models == {"claude-3-5-sonnet-20241022": 60, "gpt-4o": 40}
