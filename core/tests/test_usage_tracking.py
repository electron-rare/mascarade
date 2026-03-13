"""Tests for usage tracking integration with router."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router


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
