"""Tests pour le routeur LLM."""

import asyncio

from mascarade.router.providers.base import LLMProvider, LLMResponse, make_retry
from mascarade.router.router import Router, Strategy


class MockProvider(LLMProvider):
    def __init__(self, name: str, cost: tuple, speed: int, quality: int):
        self.name = name
        self.default_model = f"{name}-model"
        self.cost_per_million = cost
        self.speed_rank = speed
        self.quality_rank = quality

    async def send(self, messages, **kwargs):
        return LLMResponse(
            content=f"response from {self.name}",
            model=self.default_model,
            provider=self.name,
        )

    async def stream(self, messages, **kwargs):
        yield f"token from {self.name}"

    def available_models(self):
        return [self.default_model]


def _make_router() -> Router:
    r = Router()
    r._providers.clear()
    r.register(MockProvider("cheap", (1.0, 2.0), speed=2, quality=1))
    r.register(MockProvider("fast", (5.0, 10.0), speed=1, quality=2))
    r.register(MockProvider("best", (10.0, 20.0), speed=3, quality=3))
    return r


def test_available_providers():
    r = _make_router()
    assert set(r.available_providers) == {"cheap", "fast", "best"}


def test_select_cheapest():
    r = _make_router()
    provider = r._select_provider(Strategy.CHEAPEST)
    assert provider.name == "cheap"


def test_select_fastest():
    r = _make_router()
    provider = r._select_provider(Strategy.FASTEST)
    assert provider.name == "fast"


def test_select_best():
    r = _make_router()
    provider = r._select_provider(Strategy.BEST)
    assert provider.name == "best"


def test_select_specific():
    r = _make_router()
    provider = r._select_provider(Strategy.SPECIFIC, "fast")
    assert provider.name == "fast"


def test_select_specific_missing():
    r = _make_router()
    try:
        r._select_provider(Strategy.SPECIFIC, "nonexistent")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_send():
    r = _make_router()
    resp = asyncio.run(
        r.send(
            [{"role": "user", "content": "hello"}],
            strategy="cheapest",
        )
    )
    assert resp.provider == "cheap"
    assert resp.content == "response from cheap"


def test_retry_on_transient_failure():
    """Le provider retente sur erreur transitoire."""
    call_count = 0

    class FlakyProvider(LLMProvider):
        name = "flaky"
        default_model = "flaky-model"
        cost_per_million = (1.0, 1.0)
        speed_rank = 1
        quality_rank = 1

        @make_retry()
        async def send(self, messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Transient failure")
            return LLMResponse(content="ok", model="flaky-model", provider="flaky")

        async def stream(self, messages, **kwargs):
            yield "token"

        def available_models(self):
            return ["flaky-model"]

    provider = FlakyProvider()
    result = asyncio.run(provider.send([{"role": "user", "content": "test"}]))
    assert result.content == "ok"
    assert call_count == 2


def test_retry_exhausted_raises():
    """Le provider lève l'erreur après épuisement des retries."""

    class AlwaysFailProvider(LLMProvider):
        name = "fail"
        default_model = "fail-model"
        cost_per_million = (1.0, 1.0)
        speed_rank = 1
        quality_rank = 1

        @make_retry()
        async def send(self, messages, **kwargs):
            raise ConnectionError("Always fails")

        async def stream(self, messages, **kwargs):
            yield "token"

        def available_models(self):
            return ["fail-model"]

    provider = AlwaysFailProvider()
    try:
        asyncio.run(provider.send([{"role": "user", "content": "test"}]))
        assert False, "Should have raised ConnectionError"
    except ConnectionError:
        pass


def test_send_fallback_on_error():
    class FailProvider(LLMProvider):
        name = "fail"
        default_model = "fail-model"
        cost_per_million = (10.0, 10.0)
        speed_rank = 3
        quality_rank = 3

        async def send(self, messages, **kwargs):
            raise ConnectionError("forced failure")

        async def stream(self, messages, **kwargs):
            raise ConnectionError("forced failure")
            yield  # pragma: no cover

        def available_models(self):
            return [self.default_model]

    class OkProvider(LLMProvider):
        name = "ok"
        default_model = "ok-model"
        cost_per_million = (1.0, 1.0)
        speed_rank = 2
        quality_rank = 2

        async def send(self, messages, **kwargs):
            return LLMResponse(
                content="fallback-ok",
                model=self.default_model,
                provider=self.name,
                usage={"input_tokens": 10, "output_tokens": 3},
            )

        async def stream(self, messages, **kwargs):
            yield "ok"

        def available_models(self):
            return [self.default_model]

    r = Router()
    r._providers.clear()
    r.register(FailProvider())
    r.register(OkProvider())

    resp = asyncio.run(r.send([{"role": "user", "content": "hello"}], strategy="best"))
    assert resp.provider == "ok"
    assert r.fallback.get_failure_stats()["total_failures"] >= 1


def test_send_cache_hit():
    call_count = 0

    class CountProvider(LLMProvider):
        name = "count"
        default_model = "count-model"
        cost_per_million = (1.0, 1.0)
        speed_rank = 1
        quality_rank = 1

        async def send(self, messages, **kwargs):
            nonlocal call_count
            call_count += 1
            return LLMResponse(
                content="cached-response",
                model=self.default_model,
                provider=self.name,
                usage={"input_tokens": 5, "output_tokens": 2},
            )

        async def stream(self, messages, **kwargs):
            yield "cached"

        def available_models(self):
            return [self.default_model]

    r = Router()
    r._providers.clear()
    r.register(CountProvider())

    payload = [{"role": "user", "content": "cache-me"}]
    first = asyncio.run(r.send(payload, strategy="best"))
    # Force same provider selection for cache hit
    second = asyncio.run(r.send(payload, strategy="specific", provider="count"))
    assert first.content == second.content == "cached-response"
    assert call_count == 1
    assert r.cache.get_stats()["hit_count"] == 1


def test_stream_cache_hit():
    """Test that streaming responses are cached and retrieved as single event."""
    stream_call_count = 0

    class StreamCountProvider(LLMProvider):
        name = "stream-count"
        default_model = "stream-model"
        cost_per_million = (1.0, 1.0)
        speed_rank = 1
        quality_rank = 1

        async def send(self, messages, **kwargs):
            return LLMResponse(
                content="stream-cached",
                model=self.default_model,
                provider=self.name,
                usage={"input_tokens": 5, "output_tokens": 2},
            )

        async def stream(self, messages, **kwargs):
            nonlocal stream_call_count
            stream_call_count += 1
            # Yield multiple chunks to simulate real streaming
            for chunk in ["stream", "-", "cached"]:
                yield chunk

        def available_models(self):
            return [self.default_model]

    r = Router()
    r._providers.clear()
    r.register(StreamCountProvider())

    payload = [{"role": "user", "content": "stream-cache-me"}]

    # First streaming request - should hit provider and cache result
    async def first_stream():
        chunks = []
        async for chunk in r.stream(payload, strategy="best"):
            chunks.append(chunk)
        return chunks

    first_chunks = asyncio.run(first_stream())
    assert stream_call_count == 1
    assert len(first_chunks) == 3  # Multiple chunks from provider
    first_response = "".join(first_chunks)

    # Store the first response in cache for send() to populate cache
    asyncio.run(r.send(payload, strategy="best"))

    # Second streaming request - should hit cache and return single chunk
    async def second_stream():
        chunks = []
        async for chunk in r.stream(payload, strategy="specific", provider="stream-count"):
            chunks.append(chunk)
        return chunks

    second_chunks = asyncio.run(second_stream())
    second_response = "".join(second_chunks)

    # Verify cache was hit
    assert stream_call_count == 1  # Stream not called again
    assert r.cache.get_stats()["hit_count"] >= 1

    # Verify response is delivered as single event from cache
    assert len(second_chunks) == 1
    assert second_response == "stream-cached"


def test_metrics_and_load_balancer_updated():
    class MetricsProvider(LLMProvider):
        name = "metrics"
        default_model = "metrics-model"
        cost_per_million = (2.0, 4.0)
        speed_rank = 1
        quality_rank = 1

        async def send(self, messages, **kwargs):
            return LLMResponse(
                content="metrics-ok",
                model=self.default_model,
                provider=self.name,
                usage={"input_tokens": 100, "output_tokens": 20},
            )

        async def stream(self, messages, **kwargs):
            yield "m"

        def available_models(self):
            return [self.default_model]

    r = Router()
    r._providers.clear()
    r.register(MetricsProvider())

    asyncio.run(r.send([{"role": "user", "content": "metrics"}]))

    provider_stats = r.provider_metrics("metrics")
    assert provider_stats["total_requests"] == 1
    assert provider_stats["total_tokens"] == 120
    assert provider_stats["total_cost"] > 0

    lb_stats = r.load_balancer.get_load_stats()
    assert "metrics" in lb_stats["providers"]
