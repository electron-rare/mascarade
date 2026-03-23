"""Tests for the MLX-LM provider."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from mascarade.router.providers.mlx_lm import MLXLMProvider


def _make_provider(
    monkeypatch,
    *,
    enabled: bool = True,
    base_url: str = "http://localhost:8201",
    default_model: str = "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
    timeout: float = 120.0,
) -> MLXLMProvider:
    """Build a provider with getattr-safe monkeypatched settings."""
    settings_mod = "mascarade.router.providers.mlx_lm"

    # Create a fake settings object that responds to getattr with the values
    class _FakeSettings:
        mlx_lm_enabled = enabled
        mlx_lm_base_url = base_url
        mlx_lm_default_model = default_model
        mlx_lm_timeout_seconds = timeout

    monkeypatch.setattr(f"{settings_mod}.settings", _FakeSettings())
    return MLXLMProvider()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_mlx_lm_provider_init_defaults(monkeypatch):
    provider = _make_provider(monkeypatch, enabled=False)
    assert provider.name == "mlx_lm"
    assert provider.is_configured is False
    assert provider.cost_per_million == (0.0, 0.0)


def test_mlx_lm_provider_configured(monkeypatch):
    provider = _make_provider(
        monkeypatch,
        enabled=True,
        base_url="http://127.0.0.1:8201",
        default_model="my-model",
        timeout=60.0,
    )
    assert provider.is_configured is True
    assert provider.default_model == "my-model"
    assert provider._client.timeout.read == 60.0


# ---------------------------------------------------------------------------
# Model listing (mocked)
# ---------------------------------------------------------------------------


def test_available_models_success(monkeypatch):
    provider = _make_provider(monkeypatch)

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {
        "data": [
            {"id": "mlx-community/Llama-3.1-8B-4bit"},
            {"id": "mlx-community/Mistral-7B-v0.3-4bit"},
        ]
    }

    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.get.return_value = fake_response

    monkeypatch.setattr(
        "mascarade.router.providers.mlx_lm.httpx.Client",
        lambda **kwargs: fake_client,
    )

    models = provider.available_models()
    assert models == [
        "mlx-community/Llama-3.1-8B-4bit",
        "mlx-community/Mistral-7B-v0.3-4bit",
    ]


def test_available_models_fallback_on_error(monkeypatch):
    provider = _make_provider(monkeypatch, default_model="fallback-model")

    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.get.side_effect = httpx.ConnectError("refused")

    monkeypatch.setattr(
        "mascarade.router.providers.mlx_lm.httpx.Client",
        lambda **kwargs: fake_client,
    )

    models = provider.available_models()
    assert models == ["fallback-model"]


def test_available_models_uses_cache(monkeypatch):
    provider = _make_provider(monkeypatch)
    provider._models_cache = ["cached-model"]
    provider._cache_timestamp = time.time()

    # Should return cached value without HTTP call
    models = provider.available_models()
    assert models == ["cached-model"]


# ---------------------------------------------------------------------------
# Chat completion (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_success(monkeypatch):
    provider = _make_provider(monkeypatch)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "model": "test-model",
        "choices": [
            {"message": {"role": "assistant", "content": "Hello from MLX!"}}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }

    provider._client.post = AsyncMock(return_value=mock_response)

    result = await provider.send(
        [{"role": "user", "content": "Hi"}],
        model="test-model",
        system="You are helpful.",
    )

    assert result.content == "Hello from MLX!"
    assert result.provider == "mlx_lm"
    assert result.model == "test-model"
    assert result.usage["input_tokens"] == 10
    assert result.usage["output_tokens"] == 5


@pytest.mark.asyncio
async def test_send_timeout(monkeypatch):
    provider = _make_provider(monkeypatch, timeout=30.0)
    provider._client.post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))

    with pytest.raises(RuntimeError, match="MLX-LM timeout after 30s"):
        await provider.send(
            [{"role": "user", "content": "hello"}],
            model="slow-model",
            max_tokens=512,
        )


@pytest.mark.asyncio
async def test_send_with_response_format(monkeypatch):
    provider = _make_provider(monkeypatch)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "model": "test-model",
        "choices": [{"message": {"role": "assistant", "content": '{"key": "val"}'}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }

    provider._client.post = AsyncMock(return_value=mock_response)

    result = await provider.send(
        [{"role": "user", "content": "Give JSON"}],
        response_format={"type": "json_object"},
    )

    assert result.content == '{"key": "val"}'


# ---------------------------------------------------------------------------
# Streaming (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_success(monkeypatch):
    provider = _make_provider(monkeypatch)

    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        "data: [DONE]",
    ]

    async def fake_aiter_lines():
        for line in sse_lines:
            yield line

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = fake_aiter_lines

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    provider._client.stream = MagicMock(return_value=mock_ctx)

    chunks = []
    async for chunk in provider.stream(
        [{"role": "user", "content": "Hi"}],
        model="test-model",
    ):
        chunks.append(chunk)

    assert chunks == ["Hello", " world"]


@pytest.mark.asyncio
async def test_stream_skips_empty_deltas(monkeypatch):
    provider = _make_provider(monkeypatch)

    sse_lines = [
        'data: {"choices":[{"delta":{"role":"assistant"}}]}',
        'data: {"choices":[{"delta":{"content":"ok"}}]}',
        "data: [DONE]",
    ]

    async def fake_aiter_lines():
        for line in sse_lines:
            yield line

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = fake_aiter_lines

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    provider._client.stream = MagicMock(return_value=mock_ctx)

    chunks = []
    async for chunk in provider.stream(
        [{"role": "user", "content": "Hi"}],
    ):
        chunks.append(chunk)

    assert chunks == ["ok"]


# ---------------------------------------------------------------------------
# Health check (model listing acts as health check)
# ---------------------------------------------------------------------------


def test_is_model_available(monkeypatch):
    provider = _make_provider(monkeypatch)
    provider._models_cache = ["model-a", "model-b"]
    provider._cache_timestamp = time.time()

    assert provider.is_model_available("model-a") is True
    assert provider.is_model_available("model-c") is False


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_http_error(monkeypatch):
    provider = _make_provider(monkeypatch)

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error",
        request=MagicMock(),
        response=mock_response,
    )

    provider._client.post = AsyncMock(return_value=mock_response)

    with pytest.raises(httpx.HTTPStatusError):
        await provider.send([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_send_connection_error(monkeypatch):
    provider = _make_provider(monkeypatch)
    provider._client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

    # Retry decorator will retry 3 times then reraise
    with pytest.raises(httpx.ConnectError):
        await provider.send([{"role": "user", "content": "hi"}])
