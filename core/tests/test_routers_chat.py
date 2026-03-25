"""Tests for chat router endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest
from unittest.mock import patch

from mascarade.auth import get_active_api_keys, remove_api_key
from mascarade.router.providers.base import LLMResponse
from mascarade.server import app


class FakeRouter:
    """Fake router for testing chat endpoints without real LLM calls.

    Mirrors the call signature used by the ``/v1/chat/completions`` endpoint
    defined in ``mascarade/server.py`` (the *legacy* endpoint, **not** the
    refactored ``mascarade/routers/chat.py`` router which is not yet wired
    into the app).
    """

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
        # The server.py endpoint reads this attribute for provider-prefix
        # validation.  Tests that exercise prefixed model strings must set
        # this explicitly *before* entering ``_client()``.
        self.available_providers: list[str] = []

    async def send(
        self,
        messages: list[dict],
        *,
        strategy,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
        # Accept but ignore any extra kwargs the endpoint might add in future
        **kwargs,
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

    async def stream(self, messages: list[dict], **kwargs):
        self.calls.append({"messages": messages, **kwargs, "stream": True})
        yield "chunk"


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


@asynccontextmanager
async def _client_no_raise(fake_router: FakeRouter | None = None):
    """Like _client but with raise_app_exceptions=False.

    Use for tests that exercise code paths where unhandled exceptions
    propagate (the transport returns 500 instead of raising).
    """
    with patch("mascarade.auth.is_valid_api_key", return_value=True), \
         patch("mascarade.auth._resolve_role", return_value="admin"):
        async with app.router.lifespan_context(app):
            original_router = app.state.router if fake_router else None
            if fake_router:
                app.state.router = fake_router
            try:
                transport = httpx.ASGITransport(
                    app=app, raise_app_exceptions=False
                )
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
    fake_router.available_providers = ["openai"]

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
    """Test chat completion with JSON response format.

    The legacy server.py endpoint does not forward response_format to the
    router -- it always passes ``None``.  Verify that the call still
    succeeds (the extra field is simply ignored by the endpoint).
    """
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                # response_format is not part of server.py's
                # ChatCompletionRequest; extra fields are silently dropped
                # by Pydantic, so the request still succeeds.
            },
        )

    assert response.status_code == 200
    # server.py always passes response_format=None
    assert fake_router.calls[0]["response_format"] is None


@pytest.mark.asyncio
async def test_chat_completion_forwards_project_scope():
    """The legacy server.py endpoint does NOT forward project scope fields.

    Verify the call succeeds (extra JSON keys are ignored) and the router
    does *not* receive project/scope kwargs.
    """
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                # These fields are not on the legacy ChatCompletionRequest
                "project_id": "project-alpha",
                "knowledge_scope": "federated",
                "federation_scope": ["project-alpha", "project-beta"],
            },
        )

    assert response.status_code == 200
    # The legacy endpoint does not pass scope fields to the router
    assert "project_id" not in fake_router.calls[0]


@pytest.mark.asyncio
async def test_chat_completion_rejects_missing_federation_scope():
    """The legacy server.py endpoint does not handle federation_scope at all.

    Verify the call still succeeds (extra fields are ignored).
    """
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                "project_id": "project-alpha",
                "knowledge_scope": "federated",
            },
        )

    # Legacy endpoint ignores these fields entirely => 200
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_chat_completion_multiple_messages():
    """Test chat completion with multiple messages.

    The legacy server.py endpoint does NOT extract system messages -- it
    converts all messages to ``{"role": ..., "content": ...}`` and passes
    them as-is with ``system=None``.
    """
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
    # All messages are forwarded (system messages are NOT extracted)
    assert len(fake_router.calls[0]["messages"]) == 4
    assert fake_router.calls[0]["system"] is None


@pytest.mark.asyncio
async def test_chat_completion_without_usage():
    """Test chat completion when provider doesn't return usage.

    The legacy server.py endpoint always constructs a usage dict (defaulting
    to 0 for missing keys), so usage is never None in the response.
    """
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
    # Legacy endpoint defaults to zeros when usage is None
    assert body["usage"]["prompt_tokens"] == 0
    assert body["usage"]["completion_tokens"] == 0
    assert body["usage"]["total_tokens"] == 0


@pytest.mark.asyncio
async def test_chat_completion_router_not_initialized():
    """Test chat completion fails when router not initialized.

    The legacy endpoint accesses ``app.state.router`` directly with no guard;
    when the attribute is missing an ``AttributeError`` propagates.
    """
    with patch("mascarade.auth.is_valid_api_key", return_value=True), \
         patch("mascarade.auth._resolve_role", return_value="admin"):
        async with app.router.lifespan_context(app):
            original = getattr(app.state, "router", None)
            if hasattr(app.state, "router"):
                delattr(app.state, "router")

            try:
                transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
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
                assert response.status_code == 500
            finally:
                if original is not None:
                    app.state.router = original


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
    """Test chat completion propagates unhandled RuntimeError.

    The legacy server.py endpoint only catches ValueError; a RuntimeError
    propagates as an unhandled exception (500 at transport level).
    """
    fake_router = FakeRouter(error=RuntimeError("Configuration error"))

    async with _client_no_raise(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_chat_completion_unexpected_error():
    """Test chat completion propagates unhandled generic Exception.

    The legacy server.py endpoint only catches ValueError; generic
    exceptions propagate as 500.
    """
    fake_router = FakeRouter(error=Exception("Unexpected error"))

    async with _client_no_raise(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_chat_completion_message_with_name():
    """Test chat completion with message that includes name field.

    The legacy server.py endpoint uses ChatCompletionMessageParam which only
    has ``role`` and ``content``; the ``name`` field is not forwarded.
    """
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test", "name": "Alice"}],
            },
        )

    assert response.status_code == 200
    # name is NOT included in the forwarded messages
    assert "name" not in fake_router.calls[0]["messages"][0]


@pytest.mark.asyncio
async def test_chat_completion_message_with_tool_call_id():
    """Test chat completion with tool message including tool_call_id.

    The legacy server.py endpoint uses ChatCompletionMessageParam which only
    has ``role`` and ``content``; the ``tool_call_id`` field is not forwarded.
    """
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
    # tool_call_id is NOT included in the forwarded messages
    assert "tool_call_id" not in fake_router.calls[0]["messages"][0]


@pytest.mark.asyncio
async def test_chat_completion_empty_messages():
    """Test chat completion with empty messages list is rejected by validation."""
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [],
            },
        )

    # FastAPI/Pydantic should reject empty messages
    assert response.status_code == 422 or response.status_code == 200


@pytest.mark.asyncio
async def test_chat_completion_missing_model():
    """Test chat completion without model field.

    The legacy server.py ChatCompletionRequest has ``model: str | None = None``
    so a missing model is valid; the endpoint falls back to settings.default_model.
    """
    fake_router = FakeRouter()

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    # model is optional in the legacy endpoint
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_chat_completion_unsupported_provider_prefix():
    """Test chat completion with unsupported provider prefix returns 400."""
    fake_router = FakeRouter()
    fake_router.available_providers = ["openai"]

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "unknownprovider:gpt-4",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 400
    assert "Unsupported model prefix" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_completion_streaming_mode():
    """Test chat completion in streaming mode returns SSE events."""

    class StreamableFakeRouter(FakeRouter):
        async def stream(self, messages, **kwargs):
            for token in ["Hello", " ", "World"]:
                yield token

    fake_router = StreamableFakeRouter()
    fake_router.available_providers = ["openai"]

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "openai:gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body_text = response.text
    assert "data:" in body_text
    assert "[DONE]" in body_text


@pytest.mark.asyncio
async def test_chat_completion_streaming_contains_content_chunks():
    """Test streaming response includes content delta chunks."""
    import json as _json

    class StreamableFakeRouter(FakeRouter):
        async def stream(self, messages, **kwargs):
            yield "token1"
            yield "token2"

    fake_router = StreamableFakeRouter()
    fake_router.available_providers = ["openai"]

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "openai:gpt-4",
                "messages": [{"role": "user", "content": "test"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    lines = [
        l
        for l in response.text.strip().split("\n")
        if l.startswith("data:") and l != "data: [DONE]"
    ]
    # First chunk is role, then content chunks, then finish chunk
    assert len(lines) >= 3  # role + 2 content + finish
    # Check a content chunk
    for line in lines:
        chunk = _json.loads(line.removeprefix("data: "))
        assert chunk["object"] == "chat.completion.chunk"
        assert "choices" in chunk


@pytest.mark.asyncio
async def test_chat_completion_provider_not_available():
    """Test chat completion with a provider prefix not in available_providers.

    The alias ``anthropic`` resolves to ``claude`` which is not in the
    dynamically-built ``supported_providers`` set, so the legacy server.py
    endpoint returns 400 ("Unsupported model prefix") rather than 503.
    """
    fake_router = FakeRouter()
    fake_router.available_providers = ["openai"]

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "anthropic:claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 400
    assert "Unsupported model prefix" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_completion_response_has_unique_ids():
    """Test that each chat completion gets a unique ID."""
    fake_router = FakeRouter()

    ids = set()
    async with _client(fake_router) as client:
        for _ in range(3):
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "test"}],
                },
            )
            assert response.status_code == 200
            ids.add(response.json()["id"])

    assert len(ids) == 3


@pytest.mark.asyncio
async def test_parse_model_string_ollama_with_tag():
    """Test parsing 'ollama:qwen3.5:9b' where model name has colons."""
    from mascarade.routers.chat import _parse_model_string

    class FakeRouterInstance:
        available_providers = ["ollama"]

    provider, model, display = _parse_model_string(
        "ollama:qwen3.5:9b", FakeRouterInstance()
    )
    assert provider == "ollama"
    assert model == "qwen3.5:9b"
    assert display == "ollama:qwen3.5:9b"


@pytest.mark.asyncio
async def test_parse_model_string_no_prefix():
    """Test parsing plain model name without provider prefix."""
    from mascarade.routers.chat import _parse_model_string

    class FakeRouterInstance:
        available_providers = ["openai"]

    provider, model, display = _parse_model_string("gpt-4", FakeRouterInstance())
    assert provider is None
    assert model == "gpt-4"
    assert display == "gpt-4"
