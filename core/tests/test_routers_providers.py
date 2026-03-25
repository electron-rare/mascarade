"""Tests for providers router endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key
from mascarade.routers.providers import router as providers_router

TEST_API_KEY = "test-provider-key-01"


@pytest.fixture(autouse=True)
def _clean_api_keys():
    """Ensure an API key exists so auth is enforced, then clean up."""
    for key in get_active_api_keys():
        remove_api_key(key)
    add_api_key(TEST_API_KEY)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


def _make_app(fake_router=None):
    """Create a standalone test app with the providers router."""
    test_app = FastAPI()
    test_app.include_router(providers_router)
    if fake_router is not None:
        test_app.state.router = fake_router
    return test_app


class FakeRouter:
    """Fake router for testing provider endpoints."""

    def __init__(self, available_providers: list[str] | None = None):
        self.available_providers = available_providers or [
            "openai",
            "anthropic",
            "ollama",
        ]
        self._providers = {}
        self.fill_in_middle = AsyncMock(
            return_value=type(
                "Response",
                (),
                {
                    "content": "    return total\n",
                    "model": "codestral-latest",
                    "provider": "codestral",
                    "usage": {},
                },
            )()
        )

    def get_provider(self, name: str):
        """Get a provider by name."""
        return self._providers.get(name)


class FakeBedrockProvider:
    """Fake Bedrock provider for testing."""

    def list_models(self):
        """List base models."""
        return [
            "amazon.titan-text-express-v1",
            "anthropic.claude-3-sonnet-20240229-v1:0",
        ]

    def list_custom_models(self):
        """List custom fine-tuned models."""
        return [
            "arn:aws:bedrock:us-east-1:123456789012:provisioned-model/my-model",
        ]

    def list_finetune_jobs(self):
        """List fine-tuning jobs."""
        return [
            {
                "job_id": "job-123",
                "status": "InProgress",
                "model": "claude-3-sonnet",
            }
        ]


@asynccontextmanager
async def _client(fake_router: FakeRouter | None = None):
    """Create test client with optional fake router."""
    with patch("mascarade.auth.is_valid_api_key", return_value=True), \
         patch("mascarade.auth._resolve_role", return_value="admin"):
        test_app = _make_app(fake_router)
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_list_providers():
    """Test listing available providers."""
    fake_router = FakeRouter(available_providers=["openai", "anthropic", "ollama"])

    async with _client(fake_router) as client:
        response = await client.get(
            "/v1/api/providers",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "providers" in body
    assert "openai" in body["providers"]
    assert "anthropic" in body["providers"]
    assert "ollama" in body["providers"]


@pytest.mark.asyncio
async def test_providers_status():
    """Test getting provider status."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.get(
            "/v1/api/providers/status",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "providers" in body
    assert isinstance(body["providers"], list)
    # Should have providers registered in the system
    assert len(body["providers"]) > 0
    # Verify structure
    if len(body["providers"]) > 0:
        provider = body["providers"][0]
        assert "name" in provider or "provider" in provider


@pytest.mark.asyncio
async def test_update_provider_key():
    """Test updating provider API key."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.put(
            "/v1/api/providers/openai/key",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "keys": {
                    "OPENAI_API_KEY": "sk-test-key-123",
                }
            },
        )

    assert response.status_code == 200
    body = response.json()
    # Verify response is a dict (actual structure may vary)
    assert isinstance(body, dict)


@pytest.mark.asyncio
async def test_update_unknown_provider():
    """Test updating an unknown provider returns 404."""
    async with _client() as client:
        response = await client.put(
            "/v1/api/providers/unknown-provider/key",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "keys": {
                    "API_KEY": "test",
                }
            },
        )

    assert response.status_code == 404
    assert "Unknown provider" in response.json()["detail"]


@pytest.mark.asyncio
async def test_bedrock_models():
    """Test listing Bedrock models."""
    fake_router = FakeRouter()
    fake_bedrock = FakeBedrockProvider()
    fake_router._providers["bedrock"] = fake_bedrock

    async with _client(fake_router) as client:
        response = await client.get(
            "/v1/api/providers/bedrock/models",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "models" in body
    assert "custom_models" in body
    assert "amazon.titan-text-express-v1" in body["models"]
    assert len(body["custom_models"]) == 1


@pytest.mark.asyncio
async def test_bedrock_models_not_available():
    """Test listing Bedrock models when provider not available."""
    fake_router = FakeRouter()
    # Don't add bedrock provider

    async with _client(fake_router) as client:
        response = await client.get(
            "/v1/api/providers/bedrock/models",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404
    assert "not available" in response.json()["detail"]


@pytest.mark.asyncio
async def test_bedrock_finetune_jobs():
    """Test listing Bedrock fine-tune jobs."""
    fake_router = FakeRouter()
    fake_bedrock = FakeBedrockProvider()
    fake_router._providers["bedrock"] = fake_bedrock

    async with _client(fake_router) as client:
        response = await client.get(
            "/v1/api/providers/bedrock/finetune-jobs",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    jobs = response.json()
    assert isinstance(jobs, list)
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == "job-123"
    assert jobs[0]["status"] == "InProgress"


@pytest.mark.asyncio
async def test_bedrock_finetune_jobs_not_available():
    """Test listing Bedrock fine-tune jobs when provider not available."""
    fake_router = FakeRouter()
    # Don't add bedrock provider

    async with _client(fake_router) as client:
        response = await client.get(
            "/v1/api/providers/bedrock/finetune-jobs",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 404
    assert "not available" in response.json()["detail"]


@pytest.mark.asyncio
async def test_provider_endpoints_require_auth():
    """Test that provider endpoints require authentication."""
    async with _client() as client:
        response = await client.get("/v1/api/providers")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_codestral_fim_endpoint():
    fake_router = FakeRouter(available_providers=["codestral"])

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/api/providers/codestral/fim",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "prompt": "def add(a, b):\n",
                "suffix": "\nresult = add(1, 2)\n",
                "max_tokens": 64,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "codestral"
    assert "return total" in body["content"]
    fake_router.fill_in_middle.assert_awaited_once()


@pytest.mark.asyncio
async def test_codestral_fim_validation_error():
    fake_router = FakeRouter(available_providers=["codestral"])

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/api/providers/codestral/fim",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={"prompt": "", "suffix": ""},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_providers_multiple():
    """Test listing multiple providers."""
    fake_router = FakeRouter(
        available_providers=["openai", "anthropic", "ollama", "bedrock"]
    )

    async with _client(fake_router) as client:
        response = await client.get(
            "/v1/api/providers",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "providers" in body
    assert isinstance(body["providers"], list)
    assert "openai" in body["providers"]
    assert "anthropic" in body["providers"]
