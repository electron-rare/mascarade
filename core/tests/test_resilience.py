"""Tests for fallback, cache, metrics and load-balancing behavior."""

import asyncio

from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router


class FailThenOkProvider(LLMProvider):
    def __init__(self, name: str, fail_once: bool = False):
        self.name = name
        self.default_model = f"{name}-model"
        self.cost_per_million = (1.0, 1.0)
        self.speed_rank = 1
        self.quality_rank = 2
        self._fail_once = fail_once

    async def send(self, messages, **kwargs):
        if self._fail_once:
            self._fail_once = False
            raise ConnectionError("transient")
        return LLMResponse(
            content=f"ok-{self.name}",
            model=self.default_model,
            provider=self.name,
            usage={"input_tokens": 8, "output_tokens": 4},
        )

    async def stream(self, messages, **kwargs):
        yield self.name

    def available_models(self):
        return [self.default_model]


def test_fallback_cache_metrics_and_lb_stats():
    router = Router()
    router._providers.clear()

    # First provider fails once; fallback should route to second one.
    router.register(FailThenOkProvider("p1", fail_once=True))
    router.register(FailThenOkProvider("p2", fail_once=False))

    payload = [{"role": "user", "content": "hello"}]
    first = asyncio.run(router.send(payload, strategy="best"))

    # For second call, use specific provider to ensure cache hit
    # Use the provider that was actually selected in the first call
    first_provider = first.provider
    second = asyncio.run(
        router.send(payload, strategy="specific", provider=first_provider)
    )

    assert first.content.startswith("ok-")
    # Cache should work when same provider is explicitly selected
    assert second.content == first.content  # served from cache

    fallback_stats = router.fallback.get_failure_stats()
    assert fallback_stats["total_failures"] >= 1

    cache_stats = router.cache.get_stats()
    assert cache_stats["hit_count"] >= 1

    metrics = router.metrics_summary()
    assert "providers" in metrics
    assert "cache" in metrics
    assert "load_balancer" in metrics
    assert "fallback" in metrics

    # Reset endpoints logic support
    router.reset_metrics()
    assert router.cache.get_stats()["entries"] == 0
    assert router.fallback.get_failure_stats()["total_failures"] == 0
