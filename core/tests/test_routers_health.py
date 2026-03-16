"""Tests for health router endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import MagicMock

import httpx
import pytest

from mascarade.server import app


@dataclass
class FakeProviderHealth:
    """Fake provider health data."""

    is_healthy: bool
    success_rate: float
    avg_latency_ms: float
    total_requests: int
    failed_requests: int
    last_success: datetime | None
    last_failure: datetime | None
    consecutive_failures: int


class FakeHealthMonitor:
    """Fake health monitor for testing."""

    def __init__(self):
        self.last_check_time = datetime.now()

    def get_all_health(self):
        """Get health for all providers."""
        return {
            "openai": FakeProviderHealth(
                is_healthy=True,
                success_rate=0.98,
                avg_latency_ms=250.5,
                total_requests=100,
                failed_requests=2,
                last_success=datetime.now(),
                last_failure=None,
                consecutive_failures=0,
            ),
            "anthropic": FakeProviderHealth(
                is_healthy=False,
                success_rate=0.5,
                avg_latency_ms=500.0,
                total_requests=50,
                failed_requests=25,
                last_success=None,
                last_failure=datetime.now(),
                consecutive_failures=5,
            ),
        }


class FakeCircuitBreaker:
    """Fake circuit breaker for testing."""

    def get_state(self, provider: str):
        """Get circuit breaker state for a provider."""
        if provider == "anthropic":
            return "open"
        return "closed"


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


@asynccontextmanager
async def _client(fake_router: FakeRouter | None = None, fake_registry: FakeRegistry | None = None):
    """Create test client with optional fake router and registry."""
    async with app.router.lifespan_context(app):
        original_router = None
        original_registry = None

        if fake_router:
            original_router = app.state.router if hasattr(app.state, "router") else None
            app.state.router = fake_router

        if fake_registry:
            original_registry = app.state.registry if hasattr(app.state, "registry") else None
            app.state.registry = fake_registry

        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                yield client
        finally:
            if original_router:
                app.state.router = original_router
            if original_registry:
                app.state.registry = original_registry


@pytest.mark.asyncio
async def test_health_basic():
    """Test basic health check endpoint."""
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_health_with_router():
    """Test health endpoint includes provider info when router is available."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
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
    assert body["status"] == "ok"
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
    assert body["status"] == "ok"
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
    assert openai_health["is_healthy"] is True
    assert openai_health["success_rate"] == 0.98
    assert openai_health["avg_latency_ms"] == 250.5
    assert openai_health["total_requests"] == 100
    assert openai_health["failed_requests"] == 2
    assert openai_health["consecutive_failures"] == 0
    assert openai_health["circuit_breaker_state"] == "closed"

    # Check Anthropic provider health (unhealthy)
    assert "anthropic" in body["providers"]
    anthropic_health = body["providers"]["anthropic"]
    assert anthropic_health["is_healthy"] is False
    assert anthropic_health["success_rate"] == 0.5
    assert anthropic_health["consecutive_failures"] == 5
    assert anthropic_health["circuit_breaker_state"] == "open"


@pytest.mark.asyncio
async def test_provider_health_without_router():
    """Test provider health endpoint fails without router."""
    async with app.router.lifespan_context(app):
        # Remove router from app state
        if hasattr(app.state, "router"):
            delattr(app.state, "router")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
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
            assert response.json()["status"] == "ok"
