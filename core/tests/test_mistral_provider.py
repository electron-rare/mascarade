from __future__ import annotations

import pytest

openai = pytest.importorskip("openai", reason="openai not installed")

from types import SimpleNamespace
from unittest.mock import AsyncMock

from mascarade.config import settings
from mascarade.router.providers.mistral import MistralProvider

MISTRAL_SETTING_NAMES = [
    "mistral_api_key",
    "mistral_timeout_ms",
    "litellm_proxy_enabled",
    "litellm_base_url",
    "litellm_master_key",
]


@pytest.fixture(autouse=True)
def restore_mistral_settings():
    snapshot = {name: getattr(settings, name) for name in MISTRAL_SETTING_NAMES}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


class _FakeMistral:
    created: list[dict[str, object]] = []

    def __init__(self, *, api_key: str, timeout_ms: int):
        self.api_key = api_key
        self.timeout_ms = timeout_ms
        self.chat = SimpleNamespace(
            complete_async=AsyncMock(
                return_value=SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="direct-ok"))],
                    usage=SimpleNamespace(prompt_tokens=2, completion_tokens=1),
                )
            ),
            stream_async=AsyncMock(),
        )
        self.__class__.created.append({"api_key": api_key, "timeout_ms": timeout_ms})


class _FakeAsyncOpenAI:
    created: list[dict[str, object]] = []

    def __init__(self, *, api_key: str, base_url: str, timeout: float):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(
                    return_value=SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="proxy-ok"))],
                        usage=SimpleNamespace(prompt_tokens=4, completion_tokens=3),
                    )
                )
            )
        )
        self.__class__.created.append(
            {"api_key": api_key, "base_url": base_url, "timeout": timeout}
        )


@pytest.mark.asyncio
async def test_mistral_provider_uses_direct_sdk_by_default(monkeypatch):
    settings.mistral_api_key = "mistral_api_key_123456789"  # noqa: S105
    settings.litellm_proxy_enabled = False
    _FakeMistral.created.clear()
    monkeypatch.setattr("mascarade.router.providers.mistral.Mistral", _FakeMistral)
    monkeypatch.setattr("openai.AsyncOpenAI", _FakeAsyncOpenAI)

    provider = MistralProvider()
    response = await provider.send([{"role": "user", "content": "ping"}])

    assert provider.is_configured is True
    assert _FakeMistral.created[-1]["api_key"] == "mistral_api_key_123456789"  # noqa: S105
    assert response.content == "direct-ok"


@pytest.mark.asyncio
async def test_mistral_provider_uses_litellm_proxy_when_enabled(monkeypatch):
    settings.mistral_api_key = "mistral_api_key_123456789"  # noqa: S105
    settings.litellm_proxy_enabled = True
    settings.litellm_base_url = "http://litellm:4000"
    settings.litellm_master_key = "sk-litellm-test"  # noqa: S105
    _FakeAsyncOpenAI.created.clear()
    monkeypatch.setattr("mascarade.router.providers.mistral.Mistral", _FakeMistral)
    monkeypatch.setattr("openai.AsyncOpenAI", _FakeAsyncOpenAI)

    provider = MistralProvider()
    response = await provider.send([{"role": "user", "content": "trace me"}])

    assert provider.is_configured is True
    assert _FakeAsyncOpenAI.created[-1]["api_key"] == "sk-litellm-test"  # noqa: S105
    assert _FakeAsyncOpenAI.created[-1]["base_url"] == "http://litellm:4000"
    assert response.content == "proxy-ok"
