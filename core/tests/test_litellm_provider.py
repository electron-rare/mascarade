from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mascarade.config import settings
from mascarade.router.providers.litellm import LiteLLMProvider

LITELLM_SETTING_NAMES = [
    "litellm_enabled",
    "litellm_base_url",
    "litellm_master_key",
    "litellm_timeout_seconds",
]


@pytest.fixture(autouse=True)
def restore_litellm_settings():
    snapshot = {name: getattr(settings, name) for name in LITELLM_SETTING_NAMES}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


def _make_response(content: str = "litellm-ok", status_code: int = 200) -> httpx.Response:
    body = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 6, "completion_tokens": 14},
    }
    return httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("POST", "http://litellm:4000/chat/completions"),
    )


def _make_models_response() -> httpx.Response:
    body = {
        "data": [
            {"id": "gpt-4o"},
            {"id": "claude-sonnet-4-6"},
        ]
    }
    return httpx.Response(
        status_code=200,
        json=body,
        request=httpx.Request("GET", "http://litellm:4000/models"),
    )


@pytest.mark.asyncio
async def test_litellm_send(monkeypatch):
    settings.litellm_enabled = True
    settings.litellm_base_url = "http://litellm:4000"
    settings.litellm_master_key = "sk-litellm-key-123456789"  # noqa: S105
    settings.litellm_timeout_seconds = 30.0

    provider = LiteLLMProvider()
    mock_post = AsyncMock(return_value=_make_response())
    monkeypatch.setattr(provider._client, "post", mock_post)

    response = await provider.send([{"role": "user", "content": "hello"}])

    assert response.content == "litellm-ok"
    assert response.provider == "litellm"
    assert response.usage["input_tokens"] == 6
    assert response.usage["output_tokens"] == 14
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs.args[0] == "/chat/completions"


@pytest.mark.asyncio
async def test_litellm_stream(monkeypatch):
    settings.litellm_enabled = True
    settings.litellm_base_url = "http://litellm:4000"
    settings.litellm_master_key = "sk-litellm-key-123456789"  # noqa: S105
    settings.litellm_timeout_seconds = 30.0

    sse_lines = [
        'data: {"choices":[{"delta":{"content":"hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        "data: [DONE]",
    ]

    class _FakeStreamResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            for line in sse_lines:
                yield line

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    provider = LiteLLMProvider()
    monkeypatch.setattr(provider._client, "stream", MagicMock(return_value=_FakeStreamResponse()))

    chunks = []
    async for chunk in provider.stream([{"role": "user", "content": "hi"}]):
        chunks.append(chunk)

    assert chunks == ["hello", " world"]


def test_litellm_available_models(monkeypatch):
    settings.litellm_enabled = True
    settings.litellm_base_url = "http://litellm:4000"
    settings.litellm_master_key = "sk-litellm-key-123456789"  # noqa: S105
    settings.litellm_timeout_seconds = 30.0

    provider = LiteLLMProvider()

    with patch("mascarade.router.providers.litellm.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = _make_models_response()
        mock_client_cls.return_value = mock_client

        models = provider.available_models()

    assert "gpt-4o" in models
    assert "claude-sonnet-4-6" in models


def test_litellm_is_configured_requires_all_three():
    settings.litellm_enabled = True
    settings.litellm_base_url = "http://litellm:4000"
    settings.litellm_master_key = "sk-litellm-key-123456789"  # noqa: S105
    provider = LiteLLMProvider()
    assert provider.is_configured is True


def test_litellm_not_configured_when_disabled():
    settings.litellm_enabled = False
    settings.litellm_base_url = "http://litellm:4000"
    settings.litellm_master_key = "sk-litellm-key-123456789"  # noqa: S105
    provider = LiteLLMProvider()
    assert provider.is_configured is False


def test_litellm_not_configured_when_no_url():
    settings.litellm_enabled = True
    settings.litellm_base_url = ""
    settings.litellm_master_key = "sk-litellm-key-123456789"  # noqa: S105
    provider = LiteLLMProvider()
    assert provider.is_configured is False


def test_litellm_not_configured_when_no_key():
    settings.litellm_enabled = True
    settings.litellm_base_url = "http://litellm:4000"
    settings.litellm_master_key = ""
    provider = LiteLLMProvider()
    assert provider.is_configured is False
