"""Tests for OpenAIProvider — litellm-based implementation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.config import settings
from mascarade.router.providers.openai import OpenAIProvider

OPENAI_SETTING_NAMES = [
    "openai_api_key",
]


@pytest.fixture(autouse=True)
def restore_openai_settings():
    snapshot = {name: getattr(settings, name) for name in OPENAI_SETTING_NAMES}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


@pytest.mark.asyncio
async def test_openai_send():
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "openai-ok"
    mock_response.usage.prompt_tokens = 8
    mock_response.usage.completion_tokens = 12

    with patch("mascarade.router.providers.openai.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        provider = OpenAIProvider()
        assert provider.is_configured is True
        response = await provider.send([{"role": "user", "content": "hello"}])

    assert response.content == "openai-ok"
    assert response.provider == "openai"
    assert response.usage["input_tokens"] == 8
    assert response.usage["output_tokens"] == 12


@pytest.mark.asyncio
async def test_openai_proxy_send():
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "openai-ok"
    mock_response.usage.prompt_tokens = 8
    mock_response.usage.completion_tokens = 12

    with patch("mascarade.router.providers.openai.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        provider = OpenAIProvider()
        response = await provider.send([{"role": "user", "content": "hello"}])

    assert response.content == "openai-ok"


@pytest.mark.asyncio
async def test_openai_stream():
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105

    async def fake_stream(*args, **kwargs):
        for text in ["foo", "bar"]:
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
            )

    with patch("mascarade.router.providers.openai.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=fake_stream())
        provider = OpenAIProvider()
        result = []
        async for chunk in provider.stream([{"role": "user", "content": "hi"}]):
            result.append(chunk)

    assert result == ["foo", "bar"]


def test_openai_available_models():
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105
    with patch("mascarade.router.providers.openai.litellm", new=MagicMock()):
        provider = OpenAIProvider()
        models = provider.available_models()
    assert isinstance(models, list)
    assert "gpt-4o" in models


def test_openai_not_configured_when_no_key():
    settings.openai_api_key = ""
    with patch("mascarade.router.providers.openai.litellm", new=MagicMock()):
        provider = OpenAIProvider()
        assert provider.is_configured is False


@pytest.mark.asyncio
async def test_openai_send_with_system():
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "openai-ok"
    mock_response.usage.prompt_tokens = 8
    mock_response.usage.completion_tokens = 12

    with patch("mascarade.router.providers.openai.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        provider = OpenAIProvider()
        response = await provider.send(
            [{"role": "user", "content": "hi"}],
            system="Be concise.",
        )
    assert response.content == "openai-ok"


@pytest.mark.asyncio
async def test_openai_send_default_model():
    settings.openai_api_key = "sk-openai-test-key-123456789"  # noqa: S105

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "openai-ok"
    mock_response.usage.prompt_tokens = 8
    mock_response.usage.completion_tokens = 12

    with patch("mascarade.router.providers.openai.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        provider = OpenAIProvider()
        response = await provider.send([{"role": "user", "content": "hi"}])
    assert response.model == "gpt-4o"
