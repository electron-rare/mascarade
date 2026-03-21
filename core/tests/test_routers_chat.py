"""Tests for chat router endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest

from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key
from mascarade.router.providers.base import LLMResponse
from mascarade.server import app


class FakeRouter:
    """Fake router for testing chat endpoints without real LLM calls."""

    def __init__(
        self,
        *,
        response: LLMResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self._response = response or LLMResponse(
            content="Test response",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        self._error = error
        self.calls: list[dict] = []

    async def send(
        self,
        messages: list[dict],
        *,
        strategy,
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
async def test_chat_completion_basic():
    """Test basic chat completion request."""
    fake_router = FakeRouter(
        response=LLMResponse(
            content="Hello! How can I help you?",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 15, "output_tokens": 8},
        )
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

    assert response.status_code == 200
    body = response.json()

    # Verify OpenAI-compatible structure
    assert "id" in body
    assert "object" in body
    assert "created" in body
    assert "model" in body
    assert "choices" in body
    assert "usage" in body

    assert body["object"] == "chat.completion"
    assert body["model"] == "gpt-4"
    assert len(body["choices"]) == 1

    # Verify choice structure
    choice = body["choices"][0]
    assert choice["index"] == 0
    assert choice["message"]["role"] == "assistant"
    assert choice["message"]["content"] == "Hello! How can I help you?"
    assert choice["finish_reason"] == "stop"

    # Verify usage
    assert body["usage"]["prompt_tokens"] == 15
    assert body["usage"]["completion_tokens"] == 8
    assert body["usage"]["total_tokens"] == 23


@pytest.mark.asyncio
async def test_chat_completion_with_provider_prefix():
    """Test chat completion with provider:model format."""
    fake_router = FakeRouter(
        response=LLMResponse(
            content="Response",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 5, "output_tokens": 2},
        )
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "openai:gpt-4",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 200
    # Verify the router received the correct provider
    assert fake_router.calls[0]["provider"] == "openai"
    assert fake_router.calls[0]["model"] == "gpt-4"


@pytest.mark.asyncio
async def test_chat_completion_with_temperature():
    """Test chat completion with custom temperature."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                "temperature": 0.9,
            },
        )

    assert response.status_code == 200
    assert fake_router.calls[0]["temperature"] == 0.9


@pytest.mark.asyncio
async def test_chat_completion_with_max_tokens():
    """Test chat completion with custom max_tokens."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 100,
            },
        )

    assert response.status_code == 200
    assert fake_router.calls[0]["max_tokens"] == 100


@pytest.mark.asyncio
async def test_chat_completion_default_max_tokens():
    """Test chat completion uses default max_tokens when not specified."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 200
    assert fake_router.calls[0]["max_tokens"] == 4096


@pytest.mark.asyncio
async def test_chat_completion_with_response_format():
    """Test chat completion with JSON response format."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                "response_format": {"type": "json_object"},
            },
        )

    assert response.status_code == 200
    assert fake_router.calls[0]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_chat_completion_multiple_messages():
    """Test chat completion with multiple messages."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                    {"role": "user", "content": "How are you?"},
                ],
            },
        )

    assert response.status_code == 200
    # System messages are extracted and passed as system= kwarg
    assert len(fake_router.calls[0]["messages"]) == 3
    assert fake_router.calls[0]["system"] == "You are helpful"


@pytest.mark.asyncio
async def test_chat_completion_without_usage():
    """Test chat completion when provider doesn't return usage."""
    fake_router = FakeRouter(
        response=LLMResponse(
            content="Response",
            model="gpt-4",
            provider="openai",
            usage=None,
        )
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["usage"] is None


@pytest.mark.asyncio
async def test_chat_completion_router_not_initialized():
    """Test chat completion fails gracefully when router not initialized."""
    async with app.router.lifespan_context(app):
        # Remove router from app state
        delattr(app.state, "router")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "test"}],
                },
            )

    assert response.status_code == 503
    assert "Router not initialized" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_completion_value_error():
    """Test chat completion handles validation errors."""
    fake_router = FakeRouter(error=ValueError("Invalid provider"))

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "invalid-model",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 400
    assert "Invalid provider" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_completion_runtime_error():
    """Test chat completion handles runtime errors."""
    fake_router = FakeRouter(error=RuntimeError("Configuration error"))

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 503
    assert "Configuration error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_completion_unexpected_error():
    """Test chat completion handles unexpected errors."""
    fake_router = FakeRouter(error=Exception("Unexpected error"))

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_completion_message_with_name():
    """Test chat completion with message that includes name field."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "user", "content": "test", "name": "Alice"}
                ],
            },
        )

    assert response.status_code == 200
    assert fake_router.calls[0]["messages"][0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_chat_completion_message_with_tool_call_id():
    """Test chat completion with tool message including tool_call_id."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "tool", "content": "result", "tool_call_id": "call_123"}
                ],
            },
        )

    assert response.status_code == 200
    assert fake_router.calls[0]["messages"][0]["tool_call_id"] == "call_123"
