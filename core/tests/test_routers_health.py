"""Tests for health router endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI

from mascarade.router.circuit_breaker import CircuitState
from mascarade.routers.health import router as health_router


@dataclass
class FakeProviderHealth:
    """Fake provider health data matching ProviderHealth schema."""

    provider_name: str
    health_score: float = 1.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    error_rate: float = 0.0
    availability: float = 1.0
    total_requests: int = 0


class FakeHealthMonitor:
    """Fake health monitor for testing."""

    def __init__(self):
        self.last_check_time = datetime.now()

    def get_all_health(self):
        """Get health for all providers."""
        return {
            "openai": FakeProviderHealth(
                provider_name="openai",
                health_score=0.98,
                latency_p50=200.0,
                latency_p95=250.5,
                latency_p99=300.0,
                error_rate=0.02,
                availability=0.98,
                total_requests=100,
            ),
            "anthropic": FakeProviderHealth(
                provider_name="anthropic",
                health_score=0.5,
                latency_p50=400.0,
                latency_p95=500.0,
                latency_p99=600.0,
                error_rate=0.5,
                availability=0.5,
                total_requests=50,
            ),
        }


class FakeCircuitBreaker:
    """Fake circuit breaker for testing."""

    def get_state(self, provider: str):
        """Get circuit breaker state for a provider."""
        if provider == "anthropic":
            return CircuitState.OPEN
        return CircuitState.CLOSED


class FakeRouter:
    """Fake router with health monitoring."""

    def __init__(self):
        self.available_providers = ["openai", "anthropic", "ollama"]
        self.health_monitor = FakeHealthMonitor()
        self.circuit_breaker = FakeCircuitBreaker()


class FakeRegistry:
    """Fake agent registry."""

    def __len__(self):
        return 5


def _make_app(fake_router=None, fake_registry=None):
    """Create a standalone test app with the health router."""
    test_app = FastAPI()
    test_app.include_router(health_router)
    if fake_router is not None:
        test_app.state.router = fake_router
    if fake_registry is not None:
        test_app.state.registry = fake_registry
    return test_app


@asynccontextmanager
async def _client(
    fake_router: FakeRouter | None = None, fake_registry: FakeRegistry | None = None
):
    """Create test client with optional fake router and registry."""
    with patch("mascarade.auth.is_valid_api_key", return_value=True), \
         patch("mascarade.auth._resolve_role", return_value="admin"):
        test_app = _make_app(fake_router, fake_registry)
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            client._test_app = test_app
            yield client


@pytest.mark.asyncio
async def test_health_basic():
    """Test basic health check endpoint."""
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert body["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_with_router():
    """Test health endpoint includes provider info when router is available."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "providers" in body
    assert "openai" in body["providers"]
    assert "anthropic" in body["providers"]
    assert "ollama" in body["providers"]


@pytest.mark.asyncio
async def test_health_with_registry():
    """Test health endpoint includes agent count when registry is available."""
    fake_registry = FakeRegistry()

    async with _client(fake_registry=fake_registry) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "agents" in body
    assert body["agents"] == 5


@pytest.mark.asyncio
async def test_health_complete():
    """Test health endpoint with both router and registry."""
    fake_router = FakeRouter()
    fake_registry = FakeRegistry()

    async with _client(fake_router, fake_registry) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "providers" in body
    assert "agents" in body
    assert len(body["providers"]) == 3
    assert body["agents"] == 5


@pytest.mark.asyncio
async def test_version_endpoint():
    """Test version endpoint."""
    async with _client() as client:
        response = await client.get("/v1/version")

    assert response.status_code == 200
    body = response.json()
    assert "version" in body
    assert "service" in body
    assert "api_version" in body
    assert body["version"] == "v1"
    assert body["service"] == "mascarade-core"


@pytest.mark.asyncio
async def test_version_structure():
    """Test version endpoint response structure."""
    async with _client() as client:
        response = await client.get("/v1/version")

    assert response.status_code == 200
    body = response.json()

    # Verify all required fields
    assert isinstance(body["version"], str)
    assert isinstance(body["service"], str)
    assert isinstance(body["api_version"], str)

    # Verify version format
    assert body["version"].startswith("v")


@pytest.mark.asyncio
async def test_provider_health_endpoint():
    """Test provider health metrics endpoint."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.get("/health/providers")

    assert response.status_code == 200
    body = response.json()
    assert "providers" in body
    assert "timestamp" in body

    # Check OpenAI provider health
    assert "openai" in body["providers"]
    openai_health = body["providers"]["openai"]
    assert openai_health["provider_name"] == "openai"
    assert openai_health["health_score"] == 0.98
    assert openai_health["latency_p95"] == 250.5
    assert openai_health["total_requests"] == 100
    assert openai_health["error_rate"] == 0.02
    assert openai_health["circuit_breaker_state"] == "closed"

    # Check Anthropic provider health (unhealthy)
    assert "anthropic" in body["providers"]
    anthropic_health = body["providers"]["anthropic"]
    assert anthropic_health["provider_name"] == "anthropic"
    assert anthropic_health["health_score"] == 0.5
    assert anthropic_health["error_rate"] == 0.5
    assert anthropic_health["circuit_breaker_state"] == "open"


@pytest.mark.asyncio
async def test_provider_health_without_router():
    """Test provider health endpoint fails without router."""
    # Create app without setting a router on state
    async with _client() as client:
        response = await client.get("/health/providers")

    assert response.status_code == 503
    assert "Router not initialized" in response.json()["detail"]


@pytest.mark.asyncio
async def test_provider_health_timestamp():
    """Test provider health endpoint includes timestamp."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.get("/health/providers")

    assert response.status_code == 200
    body = response.json()
    assert "timestamp" in body
    # Timestamp should be an ISO format string
    assert isinstance(body["timestamp"], str)
    # Should be parseable as datetime
    datetime.fromisoformat(body["timestamp"])


@pytest.mark.asyncio
async def test_health_endpoints_no_auth_required():
    """Test that health endpoints don't require authentication."""
    async with _client() as client:
        # Test /health
        response1 = await client.get("/health")
        assert response1.status_code == 200

        # Test /v1/version
        response2 = await client.get("/v1/version")
        assert response2.status_code == 200

        # Test /health/providers (should fail for different reason)
        fake_router = FakeRouter()
    async with _client(fake_router) as client:
        response3 = await client.get("/health/providers")
        assert response3.status_code == 200


@pytest.mark.asyncio
async def test_health_multiple_calls():
    """Test multiple calls to health endpoints."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        # Make multiple calls
        for _ in range(3):
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_without_router_or_registry():
    """Test health returns healthy even without router or registry."""
    # Create app without setting router or registry on state
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "providers" not in body
    assert "agents" not in body


@pytest.mark.asyncio
async def test_version_response_fields():
    """Test that version endpoint returns exactly the expected fields."""
    async with _client() as client:
        response = await client.get("/v1/version")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "v1"
    assert body["service"] == "mascarade-core"
    assert body["api_version"] in ("0.1.0", "0.2.0")


@pytest.mark.asyncio
async def test_health_provider_count_matches():
    """Test health endpoint reports correct number of providers."""
    fake_router = FakeRouter()
    fake_router.available_providers = ["openai", "anthropic"]

    async with _client(fake_router) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert len(body["providers"]) == 2


@pytest.mark.asyncio
async def test_provider_health_all_healthy():
    """Test provider health endpoint with all healthy providers."""

    class AllHealthyMonitor:
        last_check_time = datetime.now()

        def get_all_health(self):
            return {
                "openai": FakeProviderHealth(
                    provider_name="openai",
                    health_score=1.0,
                    latency_p50=80.0,
                    latency_p95=100.0,
                    latency_p99=120.0,
                    error_rate=0.0,
                    availability=1.0,
                    total_requests=200,
                ),
            }

    class AllClosedBreaker:
        def get_state(self, provider):
            return "closed"

    class HealthyRouter:
        available_providers = ["openai"]
        health_monitor = AllHealthyMonitor()
        circuit_breaker = AllClosedBreaker()

    async with _client(HealthyRouter()) as client:
        response = await client.get("/health/providers")

    assert response.status_code == 200
    body = response.json()
    openai_health = body["providers"]["openai"]
    assert openai_health["health_score"] == 1.0
    assert openai_health["error_rate"] == 0.0
    assert openai_health["circuit_breaker_state"] == "closed"


@pytest.mark.asyncio
async def test_provider_health_circuit_breaker_open():
    """Test provider health shows circuit breaker state correctly."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.get("/health/providers")

    assert response.status_code == 200
    body = response.json()
    # Anthropic should have open circuit breaker
    assert body["providers"]["anthropic"]["circuit_breaker_state"] == "open"
    # OpenAI should have closed circuit breaker
    assert body["providers"]["openai"]["circuit_breaker_state"] == "closed"


@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Test Prometheus metrics endpoint returns text/plain."""
    async with _client() as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_health_returns_json_content_type():
    """Test health endpoint returns application/json content type."""
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_health_with_zero_agents():
    """Test health reports zero agents when registry is empty."""

    class EmptyRegistry:
        def __len__(self):
            return 0

    async with _client(fake_registry=EmptyRegistry()) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["agents"] == 0
