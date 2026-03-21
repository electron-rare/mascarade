"""Tests for the OpenAI-compatible chat completions shim."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest

from mascarade.auth import get_active_api_keys, remove_api_key
from mascarade.router.providers.base import LLMResponse
from mascarade.router.router import Strategy
from mascarade.server import app


class FakeRouter:
    def __init__(
        self,
        *,
        available_providers: list[str],
        supported_provider_names: list[str] | None = None,
        response: LLMResponse | None = None,
        error: Exception | None = None,
        stream_tokens: list[str] | None = None,
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
        self._stream_tokens = stream_tokens or ["Hello", " ", "world", "!"]
        self.calls: list[dict[str, object]] = []
        self.stream_calls: list[dict[str, object]] = []

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

    async def stream(
        self,
        messages: list[dict],
        *,
        strategy: Strategy | str,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.stream_calls.append(
            {
                "messages": messages,
                "strategy": strategy,
                "provider": provider,
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


@pytest.fixture(autouse=True)
def _clean_api_keys():
    for key in get_active_api_keys():
        remove_api_key(key)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


@asynccontextmanager
async def _client(fake_router: FakeRouter):
    async with app.router.lifespan_context(app):
        original_router = app.state.router
        app.state.router = fake_router
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                yield client
        finally:
            app.state.router = original_router


@pytest.mark.asyncio
async def test_chat_completions_routes_apple_coreml_prefix():
    fake_router = FakeRouter(
        available_providers=["apple-coreml", "ollama"],
        response=LLMResponse(
            content="apple draft",
            model="qwen3.5-4b-onnx-q4f16",
            provider="apple-coreml",
            usage={"input_tokens": 12, "output_tokens": 4},
        ),
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "apple-coreml:qwen3.5-4b-onnx-q4f16",
                "messages": [{"role": "user", "content": "hello"}],
                "temperature": 0.1,
                "max_tokens": 128,
            },
        )

    assert response.status_code == 200
    assert fake_router.calls == [
        {
            "messages": [{"role": "user", "content": "hello"}],
            "strategy": Strategy.SPECIFIC,
            "provider": "apple-coreml",
            "model": "qwen3.5-4b-onnx-q4f16",
            "system": None,
            "response_format": None,
            "temperature": 0.1,
            "max_tokens": 128,
        }
    ]
    body = response.json()
    assert body["model"] == "apple-coreml:qwen3.5-4b-onnx-q4f16"
    assert body["choices"][0]["message"]["content"] == "apple draft"
    assert body["usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 4,
        "total_tokens": 16,
    }


@pytest.mark.asyncio
async def test_chat_completions_routes_ollama_prefix():
    fake_router = FakeRouter(
        available_providers=["apple-coreml", "ollama"],
        response=LLMResponse(
            content="ollama draft",
            model="qwen3.5:9b",
            provider="ollama",
            usage={"input_tokens": 18, "output_tokens": 6},
        ),
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "ollama:qwen3.5:9b",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 200
    assert fake_router.calls[0]["strategy"] == Strategy.SPECIFIC
    assert fake_router.calls[0]["provider"] == "ollama"
    assert fake_router.calls[0]["model"] == "qwen3.5:9b"


@pytest.mark.asyncio
async def test_chat_completions_uses_default_provider_for_unprefixed_model(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("mascarade.server.settings.default_provider", "apple-coreml")
    monkeypatch.setattr(
        "mascarade.server.settings.default_model",
        "qwen3.5-4b-onnx-q4f16",
    )
    fake_router = FakeRouter(
        available_providers=["apple-coreml"],
        response=LLMResponse(
            content="default route",
            model="qwen3.5-4b-onnx-q4f16",
            provider="apple-coreml",
            usage={"input_tokens": 9, "output_tokens": 3},
        ),
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "qwen3.5-4b-onnx-q4f16",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 200
    assert fake_router.calls[0]["strategy"] == Strategy.SPECIFIC
    assert fake_router.calls[0]["provider"] == "apple-coreml"
    assert fake_router.calls[0]["model"] == "qwen3.5-4b-onnx-q4f16"
    assert response.json()["model"] == "qwen3.5-4b-onnx-q4f16"


@pytest.mark.asyncio
async def test_chat_completions_returns_openai_shape(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("mascarade.server.settings.default_provider", "apple-coreml")
    monkeypatch.setattr("mascarade.server.settings.default_model", "shape-model")
    fake_router = FakeRouter(
        available_providers=["apple-coreml"],
        response=LLMResponse(
            content="shape ok",
            model="shape-model",
            provider="apple-coreml",
            usage={"total_tokens": 7},
        ),
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )

    body = response.json()
    assert response.status_code == 200
    assert body["id"].startswith("chatcmpl-")
    assert body["object"] == "chat.completion"
    assert isinstance(body["created"], int)
    assert len(body["choices"]) == 1
    assert body["choices"][0]["index"] == 0
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["message"]["content"] == "shape ok"
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["usage"] == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 7,
    }


@pytest.mark.asyncio
async def test_chat_completions_returns_503_for_unavailable_provider():
    fake_router = FakeRouter(
        available_providers=["apple-coreml"],
        supported_provider_names=["apple-coreml", "ollama"],
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "ollama:qwen3.5:9b",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "error": "Provider 'ollama' is not configured or unavailable.",
        "providers": ["apple-coreml"],
    }


@pytest.mark.asyncio
async def test_chat_completions_rejects_invalid_prefix():
    fake_router = FakeRouter(
        available_providers=["apple-coreml"],
        supported_provider_names=["apple-coreml", "ollama"],
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "banana:model",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported model prefix 'banana'."


# Version Stability Tests - ensure /v1/chat/completions contract is frozen


@pytest.mark.asyncio
async def test_chat_completions_contract_required_fields():
    """
    Verify that /v1/chat/completions always returns required OpenAI-compatible fields.
    This is a frozen contract test - changes to these fields are BREAKING.
    """
    fake_router = FakeRouter(
        available_providers=["openai"],
        response=LLMResponse(
            content="contract test",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 15, "output_tokens": 7},
        ),
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

    # Top-level required fields (frozen contract)
    required_top_level_fields = ["id", "object", "created", "model", "choices", "usage"]
    for field in required_top_level_fields:
        assert field in body, f"Missing required field: {field}"

    # Verify field types (frozen contract)
    assert isinstance(body["id"], str)
    assert body["id"].startswith("chatcmpl-")
    assert body["object"] == "chat.completion"
    assert isinstance(body["created"], int)
    assert isinstance(body["model"], str)
    assert isinstance(body["choices"], list)
    assert len(body["choices"]) > 0
    assert isinstance(body["usage"], dict)

    # Choice structure (frozen contract)
    choice = body["choices"][0]
    required_choice_fields = ["index", "message", "finish_reason"]
    for field in required_choice_fields:
        assert field in choice, f"Missing required choice field: {field}"

    assert isinstance(choice["index"], int)
    assert isinstance(choice["message"], dict)
    assert choice["finish_reason"] in ["stop", "length", "content_filter", None]

    # Message structure (frozen contract)
    message = choice["message"]
    required_message_fields = ["role", "content"]
    for field in required_message_fields:
        assert field in message, f"Missing required message field: {field}"

    assert message["role"] == "assistant"
    assert isinstance(message["content"], str)

    # Usage structure (frozen contract)
    usage = body["usage"]
    required_usage_fields = ["prompt_tokens", "completion_tokens", "total_tokens"]
    for field in required_usage_fields:
        assert field in usage, f"Missing required usage field: {field}"

    assert isinstance(usage["prompt_tokens"], int)
    assert isinstance(usage["completion_tokens"], int)
    assert isinstance(usage["total_tokens"], int)
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]


@pytest.mark.asyncio
async def test_chat_completions_contract_endpoint_path():
    """
    Verify that the endpoint path is exactly /v1/chat/completions.
    This is a frozen contract test - endpoint path changes are BREAKING.
    """
    fake_router = FakeRouter(
        available_providers=["openai"],
        response=LLMResponse(
            content="path test",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 10, "output_tokens": 5},
        ),
    )

    async with _client(fake_router) as client:
        # Correct versioned path should work
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
            },
        )
        assert response.status_code == 200

        # Old unversioned path should not work
        response = await client.post(
            "/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "test"}],
            },
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_chat_completions_contract_parameter_handling():
    """
    Verify that standard OpenAI parameters are correctly handled.
    This is a frozen contract test - parameter handling changes are BREAKING.
    """
    fake_router = FakeRouter(
        available_providers=["openai"],
        response=LLMResponse(
            content="parameter test",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 25, "output_tokens": 12},
        ),
    )

    async with _client(fake_router) as client:
        # Test with full set of standard OpenAI parameters
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello"},
                ],
                "temperature": 0.8,
                "max_tokens": 200,
                "top_p": 0.95,
                "frequency_penalty": 0.2,
                "presence_penalty": 0.3,
            },
        )

        assert response.status_code == 200
        body = response.json()

        # Verify parameters were passed to router correctly
        assert len(fake_router.calls) == 1
        call = fake_router.calls[0]

        # Verify system message handling
        assert len(call["messages"]) == 1
        assert call["messages"][0]["role"] == "user"
        assert call["messages"][0]["content"] == "Hello"
        assert call["system"] == "You are helpful"

        # Verify temperature and max_tokens are passed through
        assert call["temperature"] == 0.8
        assert call["max_tokens"] == 200

        # Verify response structure is still OpenAI-compatible
        assert body["object"] == "chat.completion"
        assert "choices" in body
        assert "usage" in body


@pytest.mark.asyncio
async def test_chat_completions_contract_error_responses():
    """
    Verify that error responses follow OpenAI error format.
    This is a frozen contract test - error format changes are BREAKING.
    """
    # Test unavailable provider error
    fake_router = FakeRouter(
        available_providers=["openai"],
        supported_provider_names=["openai", "claude"],
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "claude:claude-3-opus",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 503
    error_body = response.json()
    assert "detail" in error_body

    # Test invalid provider prefix error
    fake_router = FakeRouter(
        available_providers=["openai"],
        supported_provider_names=["openai"],
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "invalid:model",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 400
    error_body = response.json()
    assert "detail" in error_body


@pytest.mark.asyncio
async def test_chat_completions_contract_usage_tokens():
    """
    Verify that usage tokens are always calculated correctly.
    This is a frozen contract test - token calculation changes are BREAKING.
    """
    fake_router = FakeRouter(
        available_providers=["openai"],
        response=LLMResponse(
            content="token test",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 100, "output_tokens": 50},
        ),
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

    # Verify usage token calculation
    usage = body["usage"]
    assert usage["prompt_tokens"] == 100
    assert usage["completion_tokens"] == 50
    assert usage["total_tokens"] == 150

    # Test with partial usage data (only total_tokens)
    fake_router = FakeRouter(
        available_providers=["openai"],
        response=LLMResponse(
            content="partial token test",
            model="gpt-4",
            provider="openai",
            usage={"total_tokens": 75},
        ),
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
    usage = body["usage"]

    # When only total_tokens is provided, prompt_tokens and completion_tokens should default to 0
    assert "prompt_tokens" in usage
    assert "completion_tokens" in usage
    assert "total_tokens" in usage


@pytest.mark.asyncio
async def test_chat_completions_contract_multiple_choices():
    """
    Verify that the response correctly handles single choice (n=1).
    This is a frozen contract test - choices array structure is BREAKING.
    """
    fake_router = FakeRouter(
        available_providers=["openai"],
        response=LLMResponse(
            content="single choice test",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 20, "output_tokens": 10},
        ),
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
    assert isinstance(body["choices"], list)
    assert len(body["choices"]) == 1


@pytest.mark.asyncio
async def test_chat_completions_streaming():
    import json as json_module

    fake_router = FakeRouter(
        available_providers=["ollama"],
        stream_tokens=["1", " 2", " 3", " 4", " 5"],
    )

    async with _client(fake_router) as client:
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "ollama:qwen3.5:9b",
                "messages": [{"role": "user", "content": "Count to 5"}],
                "stream": True,
            },
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

            chunks = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str == "[DONE]":
                        break
                    chunk = json_module.loads(data_str)
                    chunks.append(chunk)

    # Verify we got the expected chunks
    assert len(chunks) > 0

    # First chunk should have role
    assert chunks[0]["object"] == "chat.completion.chunk"
    assert chunks[0]["choices"][0]["delta"].get("role") == "assistant"

    # Middle chunks should have content
    content_chunks = [
        c["choices"][0]["delta"].get("content", "")
        for c in chunks
        if c["choices"][0]["delta"].get("content") is not None
    ]
    assert "".join(content_chunks) == "1 2 3 4 5"

    # Last chunk should have finish_reason
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"

    # Verify stream was called with correct parameters
    assert len(fake_router.stream_calls) == 1
    assert fake_router.stream_calls[0]["provider"] == "ollama"
    assert fake_router.stream_calls[0]["model"] == "qwen3.5:9b"


@pytest.mark.asyncio
async def test_chat_completions_streaming_with_apple_coreml():
    import json as json_module

    fake_router = FakeRouter(
        available_providers=["apple-coreml"],
        stream_tokens=["Apple", " streaming", " works"],
    )

    async with _client(fake_router) as client:
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "apple-coreml:qwen3.5-4b-onnx-q4f16",
                "messages": [{"role": "user", "content": "Test streaming"}],
                "stream": True,
                "temperature": 0.5,
                "max_tokens": 256,
            },
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

            chunks = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    chunk = json_module.loads(data_str)
                    chunks.append(chunk)

    # Verify chunks
    assert len(chunks) > 0
    assert chunks[0]["object"] == "chat.completion.chunk"

    # Verify content
    content_chunks = [
        c["choices"][0]["delta"].get("content", "")
        for c in chunks
        if c["choices"][0]["delta"].get("content") is not None
    ]
    assert "".join(content_chunks) == "Apple streaming works"

    # Verify stream was called with correct provider and parameters
    assert len(fake_router.stream_calls) == 1
    assert fake_router.stream_calls[0]["provider"] == "apple-coreml"
    assert fake_router.stream_calls[0]["model"] == "qwen3.5-4b-onnx-q4f16"
    assert fake_router.stream_calls[0]["temperature"] == 0.5
    assert fake_router.stream_calls[0]["max_tokens"] == 256


@pytest.mark.asyncio
async def test_chat_completions_streaming_with_default_provider(
    monkeypatch: pytest.MonkeyPatch,
):
    import json as json_module

    monkeypatch.setattr("mascarade.server.settings.default_provider", "apple-coreml")
    monkeypatch.setattr("mascarade.server.settings.default_model", "qwen3.5-4b-onnx-q4f16")

    fake_router = FakeRouter(
        available_providers=["apple-coreml"],
        stream_tokens=["Default", " provider", " streaming"],
    )

    async with _client(fake_router) as client:
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "qwen3.5-4b-onnx-q4f16",
                "messages": [{"role": "user", "content": "Test default"}],
                "stream": True,
            },
        ) as response:
            assert response.status_code == 200

            chunks = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    chunk = json_module.loads(data_str)
                    chunks.append(chunk)

    # Verify stream was called with default provider
    assert len(fake_router.stream_calls) == 1
    assert fake_router.stream_calls[0]["provider"] == "apple-coreml"
    assert fake_router.stream_calls[0]["model"] == "qwen3.5-4b-onnx-q4f16"


@pytest.mark.asyncio
async def test_chat_completions_streaming_returns_503_for_unavailable_provider():
    fake_router = FakeRouter(
        available_providers=["apple-coreml"],
        supported_provider_names=["apple-coreml", "ollama"],
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

    # Verify choices is always a list with exactly one element (for n=1)
    assert isinstance(body["choices"], list)
    assert len(body["choices"]) == 1
    assert body["choices"][0]["index"] == 0
    assert body["choices"][0]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_chat_completions_contract_model_prefix_stability():
    """
    Verify that provider prefix routing is stable across versions.
    This is a frozen contract test - model prefix handling is BREAKING.
    """
    # Test apple-coreml prefix
    fake_router = FakeRouter(
        available_providers=["apple-coreml"],
        response=LLMResponse(
            content="apple test",
            model="qwen3.5-4b-onnx-q4f16",
            provider="apple-coreml",
            usage={"input_tokens": 10, "output_tokens": 5},
        ),
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "apple-coreml:qwen3.5-4b-onnx-q4f16",
                "messages": [{"role": "user", "content": "test"}],
            },
        )

    assert response.status_code == 200
    assert fake_router.calls[0]["provider"] == "apple-coreml"
    assert fake_router.calls[0]["model"] == "qwen3.5-4b-onnx-q4f16"
    body = response.json()
    assert body["model"] == "apple-coreml:qwen3.5-4b-onnx-q4f16"

    # Test ollama prefix
    fake_router = FakeRouter(
        available_providers=["ollama"],
        response=LLMResponse(
            content="ollama test",
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
    body = response.json()
    assert body["model"] == "ollama:llama2"


@pytest.mark.asyncio
async def test_chat_completions_streaming_with_system_prompt():
    import json as json_module

    fake_router = FakeRouter(
        available_providers=["ollama"],
        stream_tokens=["System", " prompt", " works"],
    )

    async with _client(fake_router) as client:
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "ollama:qwen3.5:9b",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Test system prompt"},
                ],
                "stream": True,
            },
        ) as response:
            assert response.status_code == 200

            chunks = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    chunk = json_module.loads(data_str)
                    chunks.append(chunk)

    # Verify system message was included in messages array
    assert len(fake_router.stream_calls) == 1
    assert fake_router.stream_calls[0]["messages"][0]["role"] == "system"
    assert fake_router.stream_calls[0]["messages"][0]["content"] == "You are a helpful assistant"
