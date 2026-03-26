"""Tests for the Ollama-compatible shim."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import httpx
import pytest

from mascarade.auth import get_active_api_keys, remove_api_key
from mascarade.ollama_compat import (
    _build_messages,
    _build_prompt_messages,
    _extract_options,
    _parse_model,
)
from mascarade.router.providers.base import LLMResponse
from mascarade.router.router import Strategy
from mascarade.server import app

# ── Unit tests for helper functions ──


class TestParseModel:
    """Tests for _parse_model (provider:model splitting)."""

    def test_plain_ollama_model(self):
        provider, model = _parse_model("llama3:8b")
        assert provider is None
        assert model == "llama3:8b"

    def test_mascarade_provider_model(self):
        provider, model = _parse_model("claude:claude-3-5-sonnet")
        assert provider == "claude"
        assert model == "claude-3-5-sonnet"

    def test_p2p_peer_path_passthrough(self):
        provider, model = _parse_model("peer123/claude:claude-3-5-sonnet")
        assert provider is None
        assert model == "peer123/claude:claude-3-5-sonnet"

    def test_numeric_tag_not_treated_as_provider(self):
        provider, model = _parse_model("qwen2.5:7b")
        assert provider is None
        assert model == "qwen2.5:7b"

    def test_plain_model_no_colon(self):
        provider, model = _parse_model("gpt-4o")
        assert provider is None
        assert model == "gpt-4o"

    def test_openai_provider_prefix(self):
        provider, model = _parse_model("openai:gpt-4o-mini")
        assert provider == "openai"
        assert model == "gpt-4o-mini"


class TestBuildMessages:
    """Tests for _build_messages."""

    def test_extracts_messages(self):
        body = {"messages": [{"role": "user", "content": "hi"}]}
        assert _build_messages(body) == [{"role": "user", "content": "hi"}]

    def test_empty_when_no_messages(self):
        assert _build_messages({}) == []


class TestBuildPromptMessages:
    """Tests for _build_prompt_messages."""

    def test_prompt_only(self):
        body = {"prompt": "hello"}
        msgs = _build_prompt_messages(body)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "hello"

    def test_with_system(self):
        body = {"prompt": "hello", "system": "be concise"}
        msgs = _build_prompt_messages(body)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "be concise"


class TestExtractOptions:
    """Tests for _extract_options."""

    def test_default_values(self):
        opts = _extract_options({})
        assert opts["temperature"] == 0.7
        assert opts["max_tokens"] == 4096

    def test_custom_values(self):
        body = {"options": {"temperature": 0.3, "num_predict": 128}}
        opts = _extract_options(body)
        assert opts["temperature"] == 0.3
        assert opts["max_tokens"] == 128


# ── Integration tests ──


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
        strategy: Strategy | str | None = None,
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
        strategy: Strategy | str | None = None,
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
    from mascarade.ollama_compat import ollama_router

    # Ensure the ollama router is included
    _already_included = any(
        getattr(r, "path", None) == "/ollama" for r in app.routes if hasattr(r, "path")
    )
    if not _already_included:
        app.include_router(ollama_router)

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
        response = await client.get("/ollama/api/tags")

    assert response.status_code == 200
    payload = response.json()
    model_names = {model["name"] for model in payload["models"]}
    # Ollama models are listed without prefix, others with provider prefix
    assert "qwen3.5:9b" in model_names
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
            "/ollama/api/chat",
            json={
                "model": "auto",
                "stream": False,
                "messages": [{"role": "user", "content": "help me"}],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    # The ollama compat shim passes messages through to the router
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
            "/ollama/api/generate",
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

    # Verify streaming output format
    assert chunks[0]["response"] == "one"
    assert chunks[0]["done"] is False
    assert chunks[-1]["done"] is True


@pytest.mark.asyncio
async def test_ollama_root_returns_running():
    fake_router = FakeRouter(available_providers=["ollama"])

    async with _client(fake_router) as client:
        response = await client.get("/ollama/")

    assert response.status_code == 200
    assert "running" in response.text.lower()


@pytest.mark.asyncio
async def test_ollama_version_endpoint():
    fake_router = FakeRouter(available_providers=["ollama"])

    async with _client(fake_router) as client:
        response = await client.get("/ollama/api/version")

    assert response.status_code == 200
    body = response.json()
    assert "mascarade" in body["version"]


@pytest.mark.asyncio
async def test_ollama_chat_requires_model():
    fake_router = FakeRouter(available_providers=["ollama"])

    async with _client(fake_router) as client:
        response = await client.post(
            "/ollama/api/chat",
            json={"model": "", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_ollama_chat_specific_provider_routing():
    fake_router = FakeRouter(
        available_providers=["claude"],
        response=LLMResponse(
            content="routed to claude",
            model="claude-3-5-sonnet",
            provider="claude",
            usage={"input_tokens": 5, "output_tokens": 3},
        ),
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/ollama/api/chat",
            json={
                "model": "claude:claude-3-5-sonnet",
                "stream": False,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["message"]["content"] == "routed to claude"
    assert fake_router.calls[0]["provider"] == "claude"
    assert fake_router.calls[0]["strategy"] == "specific"


@pytest.mark.asyncio
async def test_ollama_chat_streaming():
    fake_router = FakeRouter(
        available_providers=["ollama"],
        stream_tokens=["hello", " world"],
    )

    async with _client(fake_router) as client:
        async with client.stream(
            "POST",
            "/ollama/api/chat",
            json={
                "model": "auto",
                "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            },
        ) as response:
            assert response.status_code == 200
            chunks = [json.loads(line) async for line in response.aiter_lines() if line]

    # First chunks have content, last is done
    assert chunks[0]["message"]["content"] == "hello"
    assert chunks[-1]["done"] is True


@pytest.mark.asyncio
async def test_ollama_generate_non_streaming():
    fake_router = FakeRouter(
        available_providers=["ollama"],
        response=LLMResponse(
            content="generated text",
            model="test",
            provider="ollama",
            usage={"input_tokens": 3, "output_tokens": 2},
        ),
    )

    async with _client(fake_router) as client:
        response = await client.post(
            "/ollama/api/generate",
            json={
                "model": "auto",
                "prompt": "count to 3",
                "stream": False,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "generated text"
    assert body["done"] is True


@pytest.mark.asyncio
async def test_ollama_show_model():
    fake_router = FakeRouter(available_providers=["ollama"])

    async with _client(fake_router) as client:
        response = await client.post(
            "/ollama/api/show",
            json={"name": "test-model"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "mascarade" in body["details"]["family"].lower()


@pytest.mark.asyncio
async def test_ollama_pull_noop():
    fake_router = FakeRouter(available_providers=["ollama"])

    async with _client(fake_router) as client:
        response = await client.post(
            "/ollama/api/pull",
            json={"name": "test-model"},
        )

    assert response.status_code == 200
    assert "mascarade" in response.json()["status"].lower()
