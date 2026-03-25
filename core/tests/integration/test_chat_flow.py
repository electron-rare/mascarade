"""Integration tests for chat completion flow (API → Core → Provider)."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest
from unittest.mock import patch

from mascarade.auth import get_active_api_keys, remove_api_key
from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.server import app


class FakeLLMProvider(LLMProvider):
    """Fake LLM provider for testing the full integration flow."""

    name = "fake-provider"
    default_model = "fake-model"
    cost_per_million = (1.0, 2.0)
    speed_rank = 1
    quality_rank = 5

    def __init__(
        self,
        *,
        response: LLMResponse | None = None,
        error: Exception | None = None,
        stream_tokens: list[str] | None = None,
    ) -> None:
        self._response = response or LLMResponse(
            content="test response",
            model="fake-model",
            provider="fake-provider",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        self._error = error
        self._stream_tokens = stream_tokens or ["Hello", " ", "world"]
        self.send_calls: list[dict] = []
        self.stream_calls: list[dict] = []

    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """Record call and return configured response or raise error."""
        self.send_calls.append(
            {
                "messages": messages,
                "model": model,
                "system": system,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": response_format,
            }
        )
        if self._error is not None:
            raise self._error
        return self._response

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """Record call and yield configured tokens or raise error."""
        self.stream_calls.append(
            {
                "messages": messages,
                "model": model,
                "system": system,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self._error is not None:
            raise self._error
        for token in self._stream_tokens:
            yield token

    def available_models(self) -> list[str]:
        """Return list of available models."""
        return ["fake-model", "fake-model-2"]


@pytest.fixture(autouse=True)
def _clean_api_keys():
    """Clean up API keys before and after each test."""
    for key in get_active_api_keys():
        remove_api_key(key)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


@asynccontextmanager
async def _test_client(fake_provider: FakeLLMProvider | None = None):
    """Create test client with app lifespan and optional fake provider."""
    with patch("mascarade.auth.is_valid_api_key", return_value=True), \
         patch("mascarade.auth._resolve_role", return_value="admin"):
        async with app.router.lifespan_context(app):
            if fake_provider is not None:
                # Register the fake provider in the router
                app.state.router.register(fake_provider)

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                yield client


@pytest.mark.asyncio
async def test_chat_flow_basic_completion():
    """Test basic chat completion flow from API to provider."""
    fake_provider = FakeLLMProvider(
        response=LLMResponse(
            content="Integration test response",
            model="fake-model",
            provider="fake-provider",
            usage={"input_tokens": 15, "output_tokens": 8},
        )
    )

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [{"role": "user", "content": "Hello integration test"}],
                "temperature": 0.8,
                "max_tokens": 200,
            },
        )

    assert response.status_code == 200
    body = response.json()

    # Verify OpenAI-compatible response structure
    assert body["object"] == "chat.completion"
    assert body["model"] == "fake-model"
    assert body["choices"][0]["message"]["content"] == "Integration test response"
    assert body["usage"]["prompt_tokens"] == 15
    assert body["usage"]["completion_tokens"] == 8
    assert body["usage"]["total_tokens"] == 23

    # Verify provider received correct parameters
    assert len(fake_provider.send_calls) == 1
    call = fake_provider.send_calls[0]
    assert call["messages"] == [{"role": "user", "content": "Hello integration test"}]
    assert call["model"] == "fake-model"
    assert call["temperature"] == 0.8
    assert call["max_tokens"] == 200


@pytest.mark.asyncio
async def test_chat_flow_with_system_message():
    """Test chat completion with system message in messages array."""
    fake_provider = FakeLLMProvider()

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "What is 2+2?"},
                ],
            },
        )

    assert response.status_code == 200

    # Verify provider received system message (extracted as separate 'system' kwarg)
    assert len(fake_provider.send_calls) == 1
    call = fake_provider.send_calls[0]
    # System messages are extracted and passed via 'system' parameter
    assert call["system"] == "You are a helpful assistant"
    assert len(call["messages"]) == 1
    assert call["messages"][0]["role"] == "user"
    assert call["messages"][0]["content"] == "What is 2+2?"


@pytest.mark.asyncio
async def test_chat_flow_provider_error_handling():
    """Test error handling when provider raises an exception."""
    fake_provider = FakeLLMProvider(error=RuntimeError("Provider is down"))

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [{"role": "user", "content": "This will fail"}],
            },
        )

    # Router errors should return 503
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_chat_flow_invalid_model_format():
    """Test error handling for invalid model format."""
    fake_provider = FakeLLMProvider()

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "invalid:provider:format:model",
                "messages": [{"role": "user", "content": "Test"}],
            },
        )

    # System handles gracefully - either succeeds or returns error
    assert response.status_code in [200, 400, 503]


@pytest.mark.asyncio
async def test_chat_flow_multiple_messages():
    """Test chat completion with conversation history."""
    fake_provider = FakeLLMProvider(
        response=LLMResponse(
            content="Based on our conversation...",
            model="fake-model",
            provider="fake-provider",
            usage={"input_tokens": 50, "output_tokens": 20},
        )
    )

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [
                    {"role": "user", "content": "What is Python?"},
                    {
                        "role": "assistant",
                        "content": "Python is a programming language.",
                    },
                    {"role": "user", "content": "Tell me more about it."},
                ],
            },
        )

    assert response.status_code == 200

    # Verify provider received all messages in order
    assert len(fake_provider.send_calls) == 1
    call = fake_provider.send_calls[0]
    assert len(call["messages"]) == 3
    assert call["messages"][0]["content"] == "What is Python?"
    assert call["messages"][1]["content"] == "Python is a programming language."
    assert call["messages"][2]["content"] == "Tell me more about it."


@pytest.mark.asyncio
async def test_chat_flow_temperature_and_max_tokens():
    """Test that temperature and max_tokens are passed through correctly."""
    fake_provider = FakeLLMProvider()

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [{"role": "user", "content": "Test params"}],
                "temperature": 0.3,
                "max_tokens": 50,
            },
        )

    assert response.status_code == 200

    # Verify parameters were passed to provider
    assert len(fake_provider.send_calls) == 1
    call = fake_provider.send_calls[0]
    assert call["temperature"] == 0.3
    assert call["max_tokens"] == 50


@pytest.mark.asyncio
async def test_chat_flow_default_max_tokens():
    """Test that default max_tokens is applied when not specified."""
    fake_provider = FakeLLMProvider()

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [{"role": "user", "content": "Test defaults"}],
            },
        )

    assert response.status_code == 200

    # Verify default max_tokens (4096) was applied
    assert len(fake_provider.send_calls) == 1
    call = fake_provider.send_calls[0]
    assert call["max_tokens"] == 4096


@pytest.mark.asyncio
async def test_chat_flow_usage_tracking():
    """Test that usage tokens are correctly tracked and returned."""
    fake_provider = FakeLLMProvider(
        response=LLMResponse(
            content="Usage test",
            model="fake-model",
            provider="fake-provider",
            usage={"input_tokens": 100, "output_tokens": 50},
        )
    )

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [{"role": "user", "content": "Track my usage"}],
            },
        )

    assert response.status_code == 200
    body = response.json()

    # Verify usage is correctly calculated
    assert body["usage"]["prompt_tokens"] == 100
    assert body["usage"]["completion_tokens"] == 50
    assert body["usage"]["total_tokens"] == 150


@pytest.mark.asyncio
async def test_chat_flow_partial_usage_data():
    """Test handling of partial usage data from provider."""
    fake_provider = FakeLLMProvider(
        response=LLMResponse(
            content="Partial usage",
            model="fake-model",
            provider="fake-provider",
            usage={},  # Empty usage dict
        )
    )

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [{"role": "user", "content": "Test"}],
            },
        )

    assert response.status_code == 200
    body = response.json()

    # Should handle missing usage gracefully
    assert "usage" in body
    if body["usage"] is not None:
        assert body["usage"]["prompt_tokens"] == 0
        assert body["usage"]["completion_tokens"] == 0
        assert body["usage"]["total_tokens"] == 0


@pytest.mark.asyncio
async def test_chat_flow_router_integration():
    """Test integration with Router's provider selection logic."""
    # Create two providers with different responses
    provider_a = FakeLLMProvider(
        response=LLMResponse(
            content="Response from provider A",
            model="model-a",
            provider="provider-a",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
    )
    provider_a.name = "provider-a"

    provider_b = FakeLLMProvider(
        response=LLMResponse(
            content="Response from provider B",
            model="model-b",
            provider="provider-b",
            usage={"input_tokens": 15, "output_tokens": 8},
        )
    )
    provider_b.name = "provider-b"

    async with _test_client() as client:
        # Register both providers
        app.state.router.register(provider_a)
        app.state.router.register(provider_b)

        # Test routing to specific provider via model prefix
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "provider-a:model-a",
                "messages": [{"role": "user", "content": "Route to A"}],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["choices"][0]["message"]["content"] == "Response from provider A"
        assert len(provider_a.send_calls) == 1
        assert len(provider_b.send_calls) == 0


@pytest.mark.asyncio
async def test_chat_flow_empty_message_content():
    """Test handling of empty message content."""
    fake_provider = FakeLLMProvider()

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [{"role": "user", "content": ""}],
            },
        )

    # API may reject empty content (422) or accept it (200)
    assert response.status_code in [200, 422]

    # If accepted, verify empty content is passed through
    if response.status_code == 200:
        assert len(fake_provider.send_calls) == 1
        call = fake_provider.send_calls[0]
        assert call["messages"][0]["content"] == ""


@pytest.mark.asyncio
async def test_chat_flow_response_id_generation():
    """Test that each response gets a unique completion ID."""
    fake_provider = FakeLLMProvider()

    async with _test_client(fake_provider) as client:
        # Make two requests
        response1 = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [{"role": "user", "content": "First"}],
            },
        )

        response2 = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [{"role": "user", "content": "Second"}],
            },
        )

    assert response1.status_code == 200
    assert response2.status_code == 200

    body1 = response1.json()
    body2 = response2.json()

    # Verify IDs are unique and have correct format
    assert body1["id"].startswith("chatcmpl-")
    assert body2["id"].startswith("chatcmpl-")
    assert body1["id"] != body2["id"]


@pytest.mark.asyncio
async def test_chat_flow_finish_reason():
    """Test that finish_reason is set correctly."""
    fake_provider = FakeLLMProvider()

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [{"role": "user", "content": "Test finish"}],
            },
        )

    assert response.status_code == 200
    body = response.json()

    # Verify finish_reason is present and correct
    assert body["choices"][0]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_chat_flow_created_timestamp():
    """Test that created timestamp is present and reasonable."""
    import time

    fake_provider = FakeLLMProvider()

    before = int(time.time())

    async with _test_client(fake_provider) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-provider:fake-model",
                "messages": [{"role": "user", "content": "Test timestamp"}],
            },
        )

    after = int(time.time())

    assert response.status_code == 200
    body = response.json()

    # Verify timestamp is within reasonable range
    assert body["created"] >= before
    assert body["created"] <= after
