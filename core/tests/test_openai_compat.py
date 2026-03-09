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
    assert body["choices"] == [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "shape ok"},
            "finish_reason": "stop",
        }
    ]
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
