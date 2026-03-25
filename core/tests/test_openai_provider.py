"""Tests for OpenAIProvider — works even without the openai SDK installed."""
from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

# ---------------------------------------------------------------------------
# Ensure 'openai' is importable even when not installed.
# ---------------------------------------------------------------------------
_openai_stub = ModuleType("openai")
_openai_stub.AsyncOpenAI = object
_openai_stub.RateLimitError = type("RateLimitError", (Exception,), {})
_openai_stub.APIConnectionError = type("APIConnectionError", (Exception,), {})
_openai_stub.APITimeoutError = type("APITimeoutError", (Exception,), {})

if "openai" not in sys.modules:
    sys.modules["openai"] = _openai_stub

from mascarade.config import settings  # noqa: E402
from mascarade.router.providers.openai import OpenAIProvider  # noqa: E402

OPENAI_SETTING_NAMES = [
    "openai_api_key",
    "litellm_proxy_enabled",
    "litellm_base_url",
    "litellm_master_key",
]


@pytest.fixture(autouse=True)
def restore_openai_settings():
    snapshot = {name: getattr(settings, name) for name in OPENAI_SETTING_NAMES}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


class _FakeAsyncOpenAI:
    def __init__(self, *, api_key, base_url=None, timeout=30.0, **kw):
        self.api_key = api_key
        self.base_url = base_url
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(
                    return_value=SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="openai-ok"))],
                        usage=SimpleNamespace(prompt_tokens=8, completion_tokens=12),
                    )
                )
            )
        )


@pytest.mark.asyncio
async def test_openai_send(monkeypatch):
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = False
    monkeypatch.setattr(
        "mascarade.router.providers.openai.openai.AsyncOpenAI",
        _FakeAsyncOpenAI,
    )
    provider = OpenAIProvider()
    response = await provider.send([{"role": "user", "content": "hello"}])

    assert provider.is_configured is True
    assert response.content == "openai-ok"
    assert response.provider == "openai"
    assert response.usage["input_tokens"] == 8
    assert response.usage["output_tokens"] == 12


@pytest.mark.asyncio
async def test_openai_proxy_send(monkeypatch):
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = True
    settings.litellm_base_url = "http://litellm:4000"
    settings.litellm_master_key = "sk-litellm-master"  # noqa: S105
    monkeypatch.setattr(
        "mascarade.router.providers.openai.openai.AsyncOpenAI",
        _FakeAsyncOpenAI,
    )
    provider = OpenAIProvider()
    response = await provider.send([{"role": "user", "content": "hello"}])

    assert response.content == "openai-ok"


@pytest.mark.asyncio
async def test_openai_stream(monkeypatch):
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = False

    chunks = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="foo"))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="bar"))]),
    ]
    fake_client = _FakeAsyncOpenAI(api_key="sk-openai-test-key-123456789")
    fake_client.chat.completions.create = AsyncMock(return_value=_async_iter(chunks))
    monkeypatch.setattr(
        "mascarade.router.providers.openai.openai.AsyncOpenAI",
        lambda **kw: fake_client,
    )
    provider = OpenAIProvider()
    result = []
    async for chunk in provider.stream([{"role": "user", "content": "hi"}]):
        result.append(chunk)

    assert result == ["foo", "bar"]


def test_openai_available_models(monkeypatch):
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = False
    monkeypatch.setattr(
        "mascarade.router.providers.openai.openai.AsyncOpenAI",
        _FakeAsyncOpenAI,
    )
    provider = OpenAIProvider()
    models = provider.available_models()
    assert isinstance(models, list)
    assert "gpt-4o" in models


def test_openai_not_configured_when_no_key():
    settings.openai_api_key = ""
    settings.litellm_proxy_enabled = False
    provider = OpenAIProvider()
    assert provider.is_configured is False


@pytest.mark.asyncio
async def test_openai_send_with_system(monkeypatch):
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = False
    monkeypatch.setattr(
        "mascarade.router.providers.openai.openai.AsyncOpenAI",
        _FakeAsyncOpenAI,
    )
    provider = OpenAIProvider()
    response = await provider.send(
        [{"role": "user", "content": "hi"}],
        system="Be concise.",
    )
    assert response.content == "openai-ok"


@pytest.mark.asyncio
async def test_openai_send_default_model(monkeypatch):
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = False
    monkeypatch.setattr(
        "mascarade.router.providers.openai.openai.AsyncOpenAI",
        _FakeAsyncOpenAI,
    )
    provider = OpenAIProvider()
    response = await provider.send([{"role": "user", "content": "hi"}])
    assert response.model == "gpt-4o"


# ---------- helpers ----------

async def _async_iter(items):
    for item in items:
        yield item
