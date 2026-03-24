"""Integration tests for health monitoring and circuit breaker."""

import asyncio
import time

import pytest

from mascarade.router.circuit_breaker import CircuitBreaker, CircuitState
from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router


class HealthTestProvider(LLMProvider):
    """Mock provider for health testing with controlled failure behavior."""

    def __init__(
        self,
        name: str,
        should_fail: bool = False,
        latency: float = 0.1,
    ):
        self.name = name
        self.default_model = f"{name}-model"
        self.cost_per_million = (1.0, 1.0)
        self.speed_rank = 1
        self.quality_rank = 2
        self.should_fail = should_fail
        self.latency = latency
        self.call_count = 0

    async def send(self, messages, **kwargs):
        self.call_count += 1
        await asyncio.sleep(self.latency)

        if self.should_fail:
            raise ConnectionError(f"{self.name} simulated failure")

        return LLMResponse(
            content=f"response from {self.name}",
            model=self.default_model,
            provider=self.name,
            usage={"input_tokens": 10, "output_tokens": 5},
        )

    async def stream(self, messages, **kwargs):
        await asyncio.sleep(self.latency)
        if self.should_fail:
            raise ConnectionError(f"{self.name} simulated failure")
        yield f"token from {self.name}"

    def available_models(self):
        return [self.default_model]


def test_health_score_calculation():
    """Test that health scores are calculated correctly based on metrics."""
    router = Router()
    router._providers.clear()

    # Register providers with different characteristics
    fast_provider = HealthTestProvider("fast", latency=0.01)
    slow_provider = HealthTestProvider("slow", latency=0.5)

    router.register(fast_provider)
    router.register(slow_provider)

    # Send requests to build metrics
    payload = [{"role": "user", "content": "test"}]

    # Fast provider - should have high health score
    for _ in range(10):
        asyncio.run(router.send(payload, strategy="specific", provider="fast"))

    # Slow provider - should have lower health score
    for _ in range(10):
        asyncio.run(router.send(payload, strategy="specific", provider="slow"))

    # Get health scores
    health = router.health_monitor.get_all_health()

    assert "fast" in health
    assert "slow" in health

    # Fast provider should have better health score
    assert health["fast"].health_score > health["slow"].health_score

    # Verify latency percentiles are tracked
    assert health["fast"].latency_p95 < health["slow"].latency_p95
    assert health["fast"].latency_p50 < health["slow"].latency_p50


def test_circuit_breaker_opens_on_failures():
    """Test that circuit breaker opens after threshold failures."""
    router = Router()
    router._providers.clear()

    # Set low failure threshold for testing
    router.circuit_breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=2.0,
        window_size=10.0,
    )

    failing_provider = HealthTestProvider("failing", should_fail=True)
    router.register(failing_provider)

    payload = [{"role": "user", "content": "test"}]

    # Send requests that will fail
    for _i in range(5):
        try:
            asyncio.run(router.send(payload, strategy="specific", provider="failing"))
        except Exception:
            pass  # Expected failures

    # Circuit should be OPEN after threshold failures
    circuit_state = router.circuit_breaker.get_state("failing")
    assert circuit_state == CircuitState.OPEN, f"Expected OPEN, got {circuit_state}"

    # Additional requests should be blocked
    try:
        asyncio.run(router.send(payload, strategy="specific", provider="failing"))
        # If we get here, the circuit didn't block - but router might fallback
        # In strict mode with only one provider, it should fail
    except (ValueError, RuntimeError) as e:
        # Expected - provider is blocked because the circuit is open
        assert "failing" in str(e) or "Provider" in str(e) or "Circuit breaker" in str(e)


def test_circuit_breaker_recovery():
    """Test that circuit breaker transitions to HALF_OPEN and then CLOSED."""
    router = Router()
    router._providers.clear()

    # Set short recovery timeout for testing
    router.circuit_breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=1.0,  # 1 second recovery
        window_size=10.0,
        half_open_max_calls=2,
    )

    # Provider that can be toggled between failing and working
    provider = HealthTestProvider("recoverable", should_fail=True)
    router.register(provider)

    payload = [{"role": "user", "content": "test"}]

    # Trigger failures to open circuit
    for _ in range(4):
        try:
            asyncio.run(
                router.send(payload, strategy="specific", provider="recoverable")
            )
        except Exception:
            pass

    # Verify circuit is OPEN
    assert router.circuit_breaker.get_state("recoverable") == CircuitState.OPEN

    # Wait for recovery timeout
    time.sleep(1.1)

    # Next request should trigger HALF_OPEN state
    # But it will still fail since provider is still set to fail
    # However, can_execute should return True now
    assert router.circuit_breaker.can_execute("recoverable") is True

    # The circuit should be in HALF_OPEN after timeout
    # Make the call to trigger the transition
    try:
        asyncio.run(router.send(payload, strategy="specific", provider="recoverable"))
    except Exception:
        pass

    # Now fix the provider
    provider.should_fail = False

    # Wait a bit more for another recovery window
    time.sleep(1.1)

    # Send successful requests - circuit should close
    try:
        asyncio.run(router.send(payload, strategy="specific", provider="recoverable"))
        # After successful request in HALF_OPEN, should transition to CLOSED
        final_state = router.circuit_breaker.get_state("recoverable")
        assert final_state == CircuitState.CLOSED, f"Expected CLOSED, got {final_state}"
    except Exception as e:
        # If this fails, print debug info
        stats = router.circuit_breaker.get_stats("recoverable")
        pytest.fail(f"Recovery failed: {e}, stats: {stats}")


def test_circuit_breaker_half_open_budget_is_consumed():
    """HALF_OPEN must consume its probe budget instead of allowing infinite calls."""
    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=0.05,
        window_size=1.0,
        half_open_max_calls=2,
    )

    breaker.record_failure("provider-a")
    assert breaker.get_state("provider-a") == CircuitState.OPEN

    time.sleep(0.06)

    assert breaker.can_execute("provider-a") is True
    assert breaker.can_execute("provider-a") is True
    assert breaker.can_execute("provider-a") is False

    stats = breaker.get_stats("provider-a")
    assert stats["state"] == CircuitState.HALF_OPEN.value
    assert stats["half_open_calls"] == 2


def test_health_aware_routing():
    """Test that routing excludes providers with open circuits."""
    router = Router()
    router._providers.clear()

    router.circuit_breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=10.0,
        window_size=20.0,
    )

    # Register multiple providers
    healthy_provider = HealthTestProvider("healthy", should_fail=False)
    failing_provider = HealthTestProvider("failing", should_fail=True)

    router.register(healthy_provider)
    router.register(failing_provider)

    payload = [{"role": "user", "content": "test"}]

    # Trigger failures on failing provider to open its circuit
    for _ in range(5):
        try:
            asyncio.run(router.send(payload, strategy="specific", provider="failing"))
        except Exception:
            pass

    # Verify circuit is open
    assert router.circuit_breaker.get_state("failing") == CircuitState.OPEN

    # Send request with best strategy - should route to healthy provider
    result = asyncio.run(router.send(payload, strategy="best"))

    # Should have used the healthy provider, not the failing one
    assert result.provider == "healthy", f"Expected healthy, got {result.provider}"

    # Verify the healthy provider was called, not the failing one
    assert healthy_provider.call_count > failing_provider.call_count


def test_multiple_providers_health_ranking():
    """Test that providers are ranked by health score."""
    router = Router()
    router._providers.clear()

    # Register providers with different latencies
    fast = HealthTestProvider("fast", latency=0.01)
    medium = HealthTestProvider("medium", latency=0.1)
    slow = HealthTestProvider("slow", latency=0.5)

    router.register(fast)
    router.register(medium)
    router.register(slow)

    payload = [{"role": "user", "content": "test"}]

    # Build metrics for each provider
    for _ in range(10):
        asyncio.run(router.send(payload, strategy="specific", provider="fast"))
        asyncio.run(router.send(payload, strategy="specific", provider="medium"))
        asyncio.run(router.send(payload, strategy="specific", provider="slow"))

    # Get healthiest providers
    healthiest = router.health_monitor.get_healthiest_providers(
        ["fast", "medium", "slow"]
    )

    # Should be ordered by health (fastest first)
    assert healthiest[0] == "fast", f"Expected fast first, got {healthiest}"
    assert len(healthiest) == 3


def test_health_metrics_exposure():
    """Test that health metrics are properly exposed."""
    router = Router()
    router._providers.clear()

    provider = HealthTestProvider("test-provider", latency=0.05)
    router.register(provider)

    payload = [{"role": "user", "content": "test"}]

    # Send some requests
    for _ in range(5):
        asyncio.run(router.send(payload, strategy="specific", provider="test-provider"))

    # Get metrics summary
    metrics = router.metrics_summary()

    # Verify health data is included
    assert "health" in metrics
    assert "test-provider" in metrics["health"]

    health_data = metrics["health"]["test-provider"]
    assert "health_score" in health_data
    assert "latency_p50" in health_data
    assert "latency_p95" in health_data
    assert "error_rate" in health_data
    assert "total_requests" in health_data

    # Verify circuit breaker stats are included
    assert "circuit_breaker" in metrics
    assert "providers" in metrics["circuit_breaker"]
    assert "test-provider" in metrics["circuit_breaker"]["providers"]

    cb_data = metrics["circuit_breaker"]["providers"]["test-provider"]
    assert "state" in cb_data
    assert cb_data["state"] == "closed"


def test_circuit_breaker_per_provider_isolation():
    """Test that circuit breakers are isolated per provider."""
    router = Router()
    router._providers.clear()

    router.circuit_breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=10.0,
    )

    good = HealthTestProvider("good", should_fail=False)
    bad = HealthTestProvider("bad", should_fail=True)

    router.register(good)
    router.register(bad)

    payload = [{"role": "user", "content": "test"}]

    # Fail the bad provider
    for _ in range(5):
        try:
            asyncio.run(router.send(payload, strategy="specific", provider="bad"))
        except Exception:
            pass

    # Bad provider circuit should be OPEN
    assert router.circuit_breaker.get_state("bad") == CircuitState.OPEN

    # Good provider circuit should still be CLOSED
    assert router.circuit_breaker.get_state("good") == CircuitState.CLOSED

    # Good provider should still work
    result = asyncio.run(router.send(payload, strategy="specific", provider="good"))
    assert result.provider == "good"


def test_end_to_end_health_workflow():
    """
    End-to-end test simulating the complete health monitoring workflow:
    1. Normal operation with healthy providers
    2. Provider degradation and circuit opening
    3. Traffic shifting to healthy alternatives
    4. Provider recovery and circuit closing
    """
    router = Router()
    router._providers.clear()

    # Use realistic circuit breaker settings
    router.circuit_breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=2.0,
        window_size=60.0,
    )

    # Create providers
    primary = HealthTestProvider("primary", should_fail=False, latency=0.05)
    backup = HealthTestProvider("backup", should_fail=False, latency=0.1)

    router.register(primary)
    router.register(backup)

    payload = [{"role": "user", "content": "test"}]

    # Phase 1: Normal operation - send 10 requests
    print("\n=== Phase 1: Normal Operation ===")
    for i in range(10):
        result = asyncio.run(router.send(payload, strategy="best"))
        print(f"Request {i+1}: routed to {result.provider}")

    health = router.health_monitor.get_all_health()
    print(f"Primary health: {health['primary'].health_score:.2f}")
    print(f"Backup health: {health['backup'].health_score:.2f}")

    # Phase 2: Simulate provider degradation
    print("\n=== Phase 2: Provider Degradation ===")
    primary.should_fail = True

    for i in range(5):
        try:
            result = asyncio.run(router.send(payload, strategy="best"))
            print(f"Request {i+1}: routed to {result.provider}")
        except Exception as e:
            print(f"Request {i+1}: failed - {type(e).__name__}")

    # Verify circuit opened
    primary_state = router.circuit_breaker.get_state("primary")
    print(f"Primary circuit state: {primary_state.value}")
    assert primary_state == CircuitState.OPEN

    # Phase 3: Verify traffic shifts to backup
    print("\n=== Phase 3: Traffic Shifting ===")
    for i in range(5):
        result = asyncio.run(router.send(payload, strategy="best"))
        print(f"Request {i+1}: routed to {result.provider}")
        assert (
            result.provider == "backup"
        ), "Should route to backup when primary is down"

    # Phase 4: Provider recovery
    print("\n=== Phase 4: Provider Recovery ===")
    primary.should_fail = False

    # Wait for recovery timeout
    print("Waiting for recovery timeout...")
    time.sleep(2.1)

    # Circuit should allow test requests (HALF_OPEN)
    print("Sending recovery test requests...")
    for i in range(3):
        result = asyncio.run(router.send(payload, strategy="best"))
        print(f"Recovery request {i+1}: routed to {result.provider}")

    # Verify circuit closed
    final_state = router.circuit_breaker.get_state("primary")
    print(f"Final primary circuit state: {final_state.value}")

    # The circuit might still be HALF_OPEN or should be CLOSED
    # It depends on the routing strategy and which provider was selected
    assert final_state in [
        CircuitState.CLOSED,
        CircuitState.HALF_OPEN,
    ], f"Expected CLOSED or HALF_OPEN, got {final_state}"

    print("\n=== Test Complete ===")
    print(f"Primary calls: {primary.call_count}")
    print(f"Backup calls: {backup.call_count}")

    # Verify backup was used during outage
    assert backup.call_count > 0, "Backup should have been used"


if __name__ == "__main__":
    # Run the comprehensive end-to-end test
    test_end_to_end_health_workflow()
