"""Tests for ClaudeProvider — works even without the anthropic SDK installed."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Ensure 'anthropic' and 'openai' are importable even when not installed.
# We inject lightweight stubs into sys.modules BEFORE importing the provider.
# ---------------------------------------------------------------------------

_anthropic_stub = ModuleType("anthropic")
_anthropic_stub.AsyncAnthropic = MagicMock  # will be replaced per-test
_anthropic_stub.RateLimitError = type("RateLimitError", (Exception,), {})
_anthropic_stub.APIConnectionError = type("APIConnectionError", (Exception,), {})
_anthropic_stub.APITimeoutError = type("APITimeoutError", (Exception,), {})

_openai_stub = ModuleType("openai")
_openai_stub.AsyncOpenAI = MagicMock
_openai_stub.RateLimitError = type("RateLimitError", (Exception,), {})
_openai_stub.APIConnectionError = type("APIConnectionError", (Exception,), {})
_openai_stub.APITimeoutError = type("APITimeoutError", (Exception,), {})

if "anthropic" not in sys.modules:
    sys.modules["anthropic"] = _anthropic_stub
if "openai" not in sys.modules:
    sys.modules["openai"] = _openai_stub

from mascarade.config import settings  # noqa: E402
from mascarade.router.providers.claude import ClaudeProvider  # noqa: E402

CLAUDE_SETTING_NAMES = [
    "anthropic_api_key",
    "litellm_proxy_enabled",
    "litellm_base_url",
    "litellm_master_key",
]


@pytest.fixture(autouse=True)
def restore_claude_settings():
    snapshot = {name: getattr(settings, name) for name in CLAUDE_SETTING_NAMES}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


# ---------- fake clients ----------


class _FakeAsyncAnthropic:
    def __init__(self, *, api_key, timeout=30.0, **kw):
        self.api_key = api_key
        self.messages = SimpleNamespace(
            create=AsyncMock(
                return_value=SimpleNamespace(
                    content=[SimpleNamespace(text="direct-ok")],
                    usage=SimpleNamespace(input_tokens=10, output_tokens=20),
                )
            ),
            stream=MagicMock(),
        )


class _FakeAsyncOpenAI:
    def __init__(self, *, api_key, base_url=None, timeout=30.0, **kw):
        self.api_key = api_key
        self.base_url = base_url
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(
                    return_value=SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="proxy-ok"))],
                        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=15),
                    )
                )
            )
        )


# ---------- tests ----------


@pytest.mark.asyncio
async def test_claude_direct_send(monkeypatch):
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = False
    monkeypatch.setattr(
        "mascarade.router.providers.claude.anthropic.AsyncAnthropic",
        _FakeAsyncAnthropic,
    )
    provider = ClaudeProvider()
    response = await provider.send([{"role": "user", "content": "hello"}])

    assert provider.is_configured is True
    assert response.content == "direct-ok"
    assert response.provider == "claude"
    assert response.usage["input_tokens"] == 10
    assert response.usage["output_tokens"] == 20


@pytest.mark.asyncio
async def test_claude_proxy_send(monkeypatch):
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = True
    settings.litellm_base_url = "http://litellm:4000"
    settings.litellm_master_key = "sk-litellm-test"  # noqa: S105
    monkeypatch.setattr(
        "mascarade.router.providers.claude.anthropic.AsyncAnthropic",
        _FakeAsyncAnthropic,
    )
    monkeypatch.setattr(
        "mascarade.router.providers.claude.openai.AsyncOpenAI",
        _FakeAsyncOpenAI,
    )
    provider = ClaudeProvider()
    response = await provider.send([{"role": "user", "content": "hello"}])

    assert response.content == "proxy-ok"
    assert response.usage["input_tokens"] == 5
    assert response.usage["output_tokens"] == 15


@pytest.mark.asyncio
async def test_claude_stream_direct(monkeypatch):
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = False

    fake = _FakeAsyncAnthropic(api_key="test")

    class _FakeStream:
        def __init__(self):
            self.text_stream = _async_iter(["chunk1", "chunk2"])

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    fake.messages.stream = MagicMock(return_value=_FakeStream())
    monkeypatch.setattr(
        "mascarade.router.providers.claude.anthropic.AsyncAnthropic",
        lambda **kw: fake,
    )
    provider = ClaudeProvider()
    chunks = []
    async for chunk in provider.stream([{"role": "user", "content": "hi"}]):
        chunks.append(chunk)

    assert chunks == ["chunk1", "chunk2"]


@pytest.mark.asyncio
async def test_claude_stream_proxy(monkeypatch):
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = True
    settings.litellm_base_url = "http://litellm:4000"
    settings.litellm_master_key = "sk-litellm-test"  # noqa: S105

    proxy_chunks = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="a"))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="b"))]),
    ]
    fake_openai = _FakeAsyncOpenAI(api_key="sk-litellm-test", base_url="http://litellm:4000")
    fake_openai.chat.completions.create = AsyncMock(return_value=_async_iter(proxy_chunks))
    monkeypatch.setattr(
        "mascarade.router.providers.claude.anthropic.AsyncAnthropic",
        _FakeAsyncAnthropic,
    )
    monkeypatch.setattr(
        "mascarade.router.providers.claude.openai.AsyncOpenAI",
        lambda **kw: fake_openai,
    )
    provider = ClaudeProvider()
    chunks = []
    async for chunk in provider.stream([{"role": "user", "content": "hi"}]):
        chunks.append(chunk)

    assert chunks == ["a", "b"]


def test_claude_available_models(monkeypatch):
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = False
    monkeypatch.setattr(
        "mascarade.router.providers.claude.anthropic.AsyncAnthropic",
        _FakeAsyncAnthropic,
    )
    provider = ClaudeProvider()
    models = provider.available_models()
    assert isinstance(models, list)
    assert any("claude" in m for m in models)


def test_claude_not_configured_when_no_key():
    settings.anthropic_api_key = ""
    settings.litellm_proxy_enabled = False
    provider = ClaudeProvider()
    assert provider.is_configured is False


@pytest.mark.asyncio
async def test_claude_send_with_system_prompt(monkeypatch):
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105
    settings.litellm_proxy_enabled = False
    monkeypatch.setattr(
        "mascarade.router.providers.claude.anthropic.AsyncAnthropic",
        _FakeAsyncAnthropic,
    )
    provider = ClaudeProvider()
    response = await provider.send(
        [{"role": "user", "content": "hi"}],
        system="You are helpful.",
    )
    assert response.content == "direct-ok"


# ---------- helpers ----------


async def _async_iter(items):
    for item in items:
        yield item
