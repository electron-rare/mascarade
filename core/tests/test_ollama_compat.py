"""Tests for the Ollama-compatible shim."""

from __future__ import annotations

import json
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
        provider_models: dict[str, list[str]] | None = None,
        response: LLMResponse | None = None,
        stream_tokens: list[str] | None = None,
    ) -> None:
        self.available_providers = available_providers
        self._provider_models = provider_models or {}
        self._response = response or LLMResponse(
            content="ok",
            model="auto-model",
            provider=available_providers[0] if available_providers else "fake",
            usage={"input_tokens": 5, "output_tokens": 2},
        )
        self._stream_tokens = stream_tokens or ["foo", "bar"]
        self.calls: list[dict[str, object]] = []
        self.stream_calls: list[dict[str, object]] = []

    async def send(
        self,
        messages: list[dict],
        *,
        strategy: Strategy | str,
        routing_policy: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **_: object,
    ) -> LLMResponse:
        self.calls.append(
            {
                "messages": messages,
                "strategy": strategy,
                "routing_policy": routing_policy,
                "provider": provider,
                "model": model,
                "system": system,
                "response_format": response_format,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self._response

    async def stream(
        self,
        messages: list[dict],
        *,
        strategy: Strategy | str,
        routing_policy: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **_: object,
    ):
        self.stream_calls.append(
            {
                "messages": messages,
                "strategy": strategy,
                "routing_policy": routing_policy,
                "provider": provider,
                "model": model,
                "system": system,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        for token in self._stream_tokens:
            yield token

    def provider_model_map(self) -> dict[str, list[str]]:
        return self._provider_models


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
async def test_ollama_tags_publish_auto_and_provider_prefixed_models():
    fake_router = FakeRouter(
        available_providers=["apple-coreml", "ollama"],
        provider_models={
            "ollama": ["qwen3.5:9b"],
            "apple-coreml": ["qwen3.5-4b-onnx-q4f16"],
        },
    )

    async with _client(fake_router) as client:
        response = await client.get("/api/tags")

    assert response.status_code == 200
    payload = response.json()
    model_names = {model["name"] for model in payload["models"]}
    assert "auto" in model_names
    assert "auto:strong" in model_names
    assert "ollama:qwen3.5:9b" in model_names
    assert "apple-coreml:qwen3.5-4b-onnx-q4f16" in model_names


@pytest.mark.asyncio
async def test_ollama_chat_auto_routes_through_routellm():
    fake_router = FakeRouter(
        available_providers=["apple-coreml", "ollama"],
        response=LLMResponse(
            content="auto selected answer",
            model="qwen3.5-4b-onnx-q4f16",
            provider="apple-coreml",
            usage={"input_tokens": 13, "output_tokens": 4},
        ),
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/api/chat",
            json={
                "model": "auto",
                "stream": False,
                "messages": [{"role": "user", "content": "help me"}],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert fake_router.calls[0]["strategy"] == Strategy.ROUTELLM
    assert fake_router.calls[0]["routing_policy"] == "auto"
    assert fake_router.calls[0]["model"] is None
    assert payload["model"] == "apple-coreml:qwen3.5-4b-onnx-q4f16"
    assert payload["message"]["content"] == "auto selected answer"
    assert payload["done"] is True


@pytest.mark.asyncio
async def test_ollama_generate_streams_ndjson():
    fake_router = FakeRouter(
        available_providers=["ollama"],
        stream_tokens=["one", " two"],
    )

    async with _client(fake_router) as client:
        async with client.stream(
            "POST",
            "/api/generate",
            json={
                "model": "auto:cheap",
                "prompt": "count",
                "stream": True,
                "system": "be concise",
            },
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("application/x-ndjson")
            chunks = [json.loads(line) async for line in response.aiter_lines() if line]

    assert fake_router.stream_calls[0]["strategy"] == Strategy.ROUTELLM
    assert fake_router.stream_calls[0]["routing_policy"] == "cheap"
    assert fake_router.stream_calls[0]["system"] == "be concise"
    assert chunks[0]["response"] == "one"
    assert chunks[0]["done"] is False
    assert chunks[-1]["done"] is True
