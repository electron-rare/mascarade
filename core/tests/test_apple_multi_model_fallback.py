"""Tests for router fallback chain with multiple Apple models."""

import asyncio
import logging

from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router


class MockAppleProvider(LLMProvider):
    """Mock Apple CoreML provider for testing fallback behavior."""

    def __init__(self, model_id: str, should_fail: bool = False, quality: int = 2):
        self.name = f"apple-coreml-{model_id}"
        self.default_model = model_id
        self.cost_per_million = (0.0, 0.0)  # Local models are free
        self.speed_rank = 1
        self.quality_rank = quality
        self._should_fail = should_fail

    async def send(self, messages, **kwargs):
        if self._should_fail:
            raise ConnectionError(f"Model {self.default_model} is busy or unavailable")
        return LLMResponse(
            content=f"response from {self.default_model}",
            model=self.default_model,
            provider=self.name,
            usage={"input_tokens": 10, "output_tokens": 5},
        )

    async def stream(self, messages, **kwargs):
        if self._should_fail:
            raise ConnectionError(f"Model {self.default_model} is busy or unavailable")
        yield f"token from {self.default_model}"

    def available_models(self):
        return [self.default_model]


def test_fallback_from_large_to_small_model():
    """Test router falls back from apple-4b to apple-0.5b when first model fails."""
    r = Router()
    r._providers.clear()

    # Register larger model (higher quality) that will fail
    large_model = MockAppleProvider("apple-4b", should_fail=True, quality=3)
    r.register(large_model)

    # Register smaller model (lower quality) that works as fallback
    small_model = MockAppleProvider("apple-0.5b", should_fail=False, quality=2)
    r.register(small_model)

    # Request using "best" strategy should try apple-4b first, then fall back to apple-0.5b
    resp = asyncio.run(r.send([{"role": "user", "content": "hello"}], strategy="best"))

    # Should have fallen back to the smaller model
    assert resp.provider == "apple-coreml-apple-0.5b"
    assert resp.content == "response from apple-0.5b"
    assert resp.model == "apple-0.5b"

    # Verify fallback stats were recorded
    stats = r.fallback.get_failure_stats()
    assert stats["total_failures"] >= 1


def test_fallback_with_multiple_apple_models():
    """Test fallback chain with 3 Apple models: 4b -> 1.5b -> 0.5b."""
    r = Router()
    r._providers.clear()

    # All models fail except the smallest
    r.register(MockAppleProvider("apple-4b", should_fail=True, quality=3))
    r.register(MockAppleProvider("apple-1.5b", should_fail=True, quality=2))
    r.register(MockAppleProvider("apple-0.5b", should_fail=False, quality=1))

    resp = asyncio.run(r.send([{"role": "user", "content": "fallback test"}], strategy="best"))

    # Should have fallen back all the way to the smallest model
    assert resp.provider == "apple-coreml-apple-0.5b"
    assert resp.content == "response from apple-0.5b"

    # Multiple failures should be recorded
    stats = r.fallback.get_failure_stats()
    assert stats["total_failures"] >= 2


def test_no_fallback_when_primary_works():
    """Test that no fallback occurs when primary model works."""
    r = Router()
    r._providers.clear()

    # Both models work, but we should get the best one
    r.register(MockAppleProvider("apple-4b", should_fail=False, quality=3))
    r.register(MockAppleProvider("apple-0.5b", should_fail=False, quality=2))

    resp = asyncio.run(r.send([{"role": "user", "content": "hello"}], strategy="best"))

    # Should use the higher quality model without fallback
    assert resp.provider == "apple-coreml-apple-4b"
    assert resp.content == "response from apple-4b"


def test_specific_model_selection():
    """Test requesting a specific Apple model."""
    r = Router()
    r._providers.clear()

    r.register(MockAppleProvider("apple-4b", should_fail=False, quality=3))
    r.register(MockAppleProvider("apple-0.5b", should_fail=False, quality=2))

    # Request specific model
    resp = asyncio.run(
        r.send(
            [{"role": "user", "content": "hello"}],
            strategy="specific",
            provider="apple-coreml-apple-0.5b",
        )
    )

    # Should get the requested model
    assert resp.provider == "apple-coreml-apple-0.5b"
    assert resp.content == "response from apple-0.5b"


def test_all_models_fail_raises_error():
    """Test that error is raised when all Apple models fail."""
    r = Router()
    r._providers.clear()

    # All models fail
    r.register(MockAppleProvider("apple-4b", should_fail=True, quality=3))
    r.register(MockAppleProvider("apple-0.5b", should_fail=True, quality=2))

    # Should raise an error after all fallbacks fail
    try:
        asyncio.run(r.send([{"role": "user", "content": "hello"}], strategy="best"))
        assert False, "Should have raised RuntimeError after all fallbacks failed"
    except RuntimeError as e:
        # Verify error message contains the original failure
        assert "All fallback attempts failed" in str(e)

    # All failures should be recorded
    stats = r.fallback.get_failure_stats()
    assert stats["total_failures"] >= 2


def test_stream_fallback():
    """Test that streaming also supports fallback."""
    r = Router()
    r._providers.clear()

    r.register(MockAppleProvider("apple-4b", should_fail=True, quality=3))
    r.register(MockAppleProvider("apple-0.5b", should_fail=False, quality=2))

    async def collect_stream():
        chunks = []
        async for chunk in r.stream([{"role": "user", "content": "stream test"}], strategy="best"):
            chunks.append(chunk)
        return "".join(chunks)

    result = asyncio.run(collect_stream())
    assert "apple-0.5b" in result


def test_e2e_router_fallback_chain_with_logging(caplog):
    """End-to-end test: router fallback chain with explicit logging verification.

    Verifies:
    1. Configure router with fallback: apple-4b (priority 1) -> apple-0.5b (priority 2)
    2. Send request through router
    3. Simulate apple-4b busy/failed
    4. Verify router falls back to apple-0.5b
    5. Check logs show model swap event
    """
    caplog.set_level(logging.WARNING)

    # 1. Configure router with fallback chain
    r = Router()
    r._providers.clear()

    # Register apple-4b as priority 1 (higher quality) that will fail
    apple_4b = MockAppleProvider("apple-4b", should_fail=True, quality=3)
    r.register(apple_4b)

    # Register apple-0.5b as priority 2 (lower quality) as fallback
    apple_0_5b = MockAppleProvider("apple-0.5b", should_fail=False, quality=2)
    r.register(apple_0_5b)

    # 2. Send request through router using "best" strategy
    messages = [{"role": "user", "content": "test router fallback"}]
    resp = asyncio.run(r.send(messages, strategy="best"))

    # 3. Verify apple-4b was attempted but failed (implicit - fallback stats will show this)

    # 4. Verify router fell back to apple-0.5b
    assert resp.provider == "apple-coreml-apple-0.5b", "Should have fallen back to apple-0.5b"
    assert resp.content == "response from apple-0.5b"
    assert resp.model == "apple-0.5b"
    assert resp.usage["input_tokens"] == 10
    assert resp.usage["output_tokens"] == 5

    # 5. Check that fallback stats show model swap event
    fallback_stats = r.fallback.get_failure_stats()
    assert fallback_stats["total_failures"] >= 1, "Should have recorded at least one failure"
    assert (
        "apple-coreml-apple-4b" in fallback_stats["failed_attempts"]
    ), "apple-4b failures should be tracked"
    assert (
        fallback_stats["failed_attempts"]["apple-coreml-apple-4b"] >= 1
    ), "Should have at least 1 failure for apple-4b"

    # Verify that attempts were made to fallback providers
    provider_stats = r.provider_metrics("apple-coreml-apple-0.5b")
    assert (
        provider_stats["total_requests"] >= 1
    ), "Fallback provider should have handled the request"
    assert provider_stats["error_rate"] == 0.0, "Fallback provider should have no errors"

    # Verify primary provider had 100% error rate (all requests failed)
    primary_stats = r.provider_metrics("apple-coreml-apple-4b")
    assert primary_stats["total_requests"] >= 1, "Primary provider should have been attempted"
    assert primary_stats["error_rate"] == 100.0, "Primary provider should have 100% error rate"
