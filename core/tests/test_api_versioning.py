"""Tests for API versioning and stability contract."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest
from unittest.mock import patch

from mascarade.api_version import API_VERSION, get_version_info
from mascarade.auth import get_active_api_keys, remove_api_key
from mascarade.router.providers.base import LLMResponse
from mascarade.router.router import Strategy
from mascarade.server import app


class FakeRouter:
    """Fake router for testing API endpoints without real LLM calls."""

    def __init__(
        self,
        *,
        available_providers: list[str],
        supported_provider_names: list[str] | None = None,
        response: LLMResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.available_providers = available_providers
        self.supported_provider_names = (
            supported_provider_names
            if supported_provider_names is not None
            else ["apple-coreml", "ollama", "openai", "claude", "mistral"]
        )
        self._response = response or LLMResponse(
            content="ok",
            model="fake-model",
            provider=available_providers[0] if available_providers else "fake",
            usage={"input_tokens": 5, "output_tokens": 2},
        )
        self._error = error
        self.calls: list[dict[str, object]] = []

    async def send(
        self,
        messages: list[dict],
        *,
        strategy: Strategy | str,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self.calls.append(
            {
                "messages": messages,
                "strategy": strategy,
                "provider": provider,
                "model": model,
                "system": system,
                "response_format": response_format,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self._error is not None:
            raise self._error
        return self._response


@pytest.fixture(autouse=True)
def _clean_api_keys():
    """Clean API keys before and after each test."""
    for key in get_active_api_keys():
        remove_api_key(key)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


@asynccontextmanager
async def _client(fake_router: FakeRouter | None = None):
    """Create test client with optional fake router."""
    with patch("mascarade.auth.is_valid_api_key", return_value=True), \
         patch("mascarade.auth._resolve_role", return_value="admin"):
        async with app.router.lifespan_context(app):
            original_router = app.state.router if fake_router else None
            if fake_router:
                app.state.router = fake_router
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


@pytest.mark.asyncio
async def test_version_endpoint_exists():
    """Test that /v1/version endpoint exists and returns correct structure."""
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
async def test_version_info_module():
    """Test that api_version module provides correct version info."""
    version_info = get_version_info()

    assert "api_version" in version_info
    assert "stability" in version_info
    assert "frozen_contracts" in version_info

    assert version_info["api_version"] == API_VERSION
    assert version_info["stability"] == "stable"
    assert "/v1/chat/completions" in version_info["frozen_contracts"]


@pytest.mark.asyncio
async def test_health_endpoint_unversioned():
    """Test that /health endpoint remains unversioned (not /v1/health)."""
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"


@pytest.mark.asyncio
async def test_frozen_contract_chat_completions():
    """Test that /v1/chat/completions contract is frozen and stable."""
    fake_router = FakeRouter(
        available_providers=["openai"],
        response=LLMResponse(
            content="test response",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 10, "output_tokens": 5},
        ),
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                "temperature": 0.7,
                "max_tokens": 100,
            },
        )

    assert response.status_code == 200
    body = response.json()

    # Verify OpenAI-compatible response structure (frozen contract)
    assert "id" in body
    assert "object" in body
    assert "created" in body
    assert "model" in body
    assert "choices" in body
    assert "usage" in body

    assert body["object"] == "chat.completion"
    assert isinstance(body["choices"], list)
    assert len(body["choices"]) > 0

    # Verify choice structure
    choice = body["choices"][0]
    assert "index" in choice
    assert "message" in choice
    assert "finish_reason" in choice

    # Verify message structure
    message = choice["message"]
    assert "role" in message
    assert "content" in message
    assert message["role"] == "assistant"
    assert message["content"] == "test response"

    # Verify usage structure
    usage = body["usage"]
    assert "prompt_tokens" in usage
    assert "completion_tokens" in usage
    assert "total_tokens" in usage
    assert usage["prompt_tokens"] == 10
    assert usage["completion_tokens"] == 5
    assert usage["total_tokens"] == 15


@pytest.mark.asyncio
async def test_protected_endpoints_have_v1_prefix():
    """Test that protected endpoints have /v1 prefix."""
    from mascarade.auth import add_api_key

    # Add test API key
    test_key = "test-key-12345"
    add_api_key(test_key)

    async with _client() as client:
        # Test /v1/api-keys endpoint (read-only, should work)
        response = await client.get(
            "/v1/api-keys",
            headers={"X-API-Key": test_key},
        )
        assert response.status_code == 200

        # Test /v1/providers endpoint
        response = await client.get(
            "/v1/providers",
            headers={"X-API-Key": test_key},
        )
        assert response.status_code == 200

        # Test /v1/agents endpoint
        response = await client.get(
            "/v1/agents",
            headers={"X-API-Key": test_key},
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_protected_endpoints_reject_unversioned_paths():
    """Test that old unversioned paths don't accidentally work."""
    from mascarade.auth import add_api_key

    test_key = "test-key-12345"
    add_api_key(test_key)

    async with _client() as client:
        # These should fail (no /v1 prefix)
        response = await client.get(
            "/api-keys",
            headers={"X-API-Key": test_key},
        )
        assert response.status_code == 404

        response = await client.get(
            "/providers",
            headers={"X-API-Key": test_key},
        )
        assert response.status_code == 404

        response = await client.get(
            "/agents",
            headers={"X-API-Key": test_key},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_cluster_endpoints_have_v1_prefix():
    """Test that cluster endpoints have /v1 prefix."""
    from mascarade.cluster import add_cluster_key

    # Add test cluster key
    test_key = "cluster-key-12345"
    add_cluster_key(test_key)

    async with _client() as client:
        # Test /v1/cluster/node/heartbeat endpoint
        response = await client.post(
            "/v1/cluster/node/heartbeat",
            headers={"X-Cluster-Key": test_key},
            json={
                "node_id": "test-node",
                "capacity": 100,
                "current_load": 50,
                "providers": ["openai"],
            },
        )
        # Should get 200 OK (valid cluster auth and payload)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_versioning_semantic_version():
    """Test that API version follows semantic versioning."""
    version_info = get_version_info()
    api_version = version_info["api_version"]

    # Should be in format X.Y.Z
    parts = api_version.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)

    major, minor, patch = parts
    # First version should be 1.0.0
    assert major == "1"


@pytest.mark.asyncio
async def test_chat_completions_endpoint_stability():
    """Test that /v1/chat/completions handles all standard OpenAI parameters."""
    fake_router = FakeRouter(
        available_providers=["openai"],
        response=LLMResponse(
            content="stable response",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 20, "output_tokens": 10},
        ),
    )

    async with _client(fake_router) as client:
        # Test with all standard parameters to ensure contract stability
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Hello"},
                ],
                "temperature": 0.5,
                "max_tokens": 150,
                "top_p": 0.9,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.1,
            },
        )

    assert response.status_code == 200
    body = response.json()

    # Verify stable response structure
    assert body["object"] == "chat.completion"
    assert body["model"] == "gpt-4"
    assert body["choices"][0]["message"]["content"] == "stable response"


@pytest.mark.asyncio
async def test_chat_completions_with_provider_prefix():
    """Test that provider-specific model routing works correctly with versioned endpoint."""
    fake_router = FakeRouter(
        available_providers=["ollama"],
        response=LLMResponse(
            content="ollama response",
            model="llama2",
            provider="ollama",
            usage={"input_tokens": 15, "output_tokens": 8},
        ),
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "ollama:llama2",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 200
    assert fake_router.calls[0]["provider"] == "ollama"
    assert fake_router.calls[0]["model"] == "llama2"
    assert fake_router.calls[0]["strategy"] == Strategy.SPECIFIC


@pytest.mark.asyncio
async def test_version_endpoint_includes_provider_info():
    """Test that /v1/version endpoint can include provider information."""
    fake_router = FakeRouter(available_providers=["openai", "claude", "ollama"])

    async with _client(fake_router) as client:
        response = await client.get("/v1/version")

    assert response.status_code == 200
    body = response.json()

    # Basic version info should always be present
    assert "version" in body
    assert "service" in body
    assert body["version"] == "v1"
