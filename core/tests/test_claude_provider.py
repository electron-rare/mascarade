"""Tests for ClaudeProvider — litellm-based implementation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.config import settings
from mascarade.router.providers.claude import ClaudeProvider

CLAUDE_SETTING_NAMES = [
    "anthropic_api_key",
]


@pytest.fixture(autouse=True)
def restore_claude_settings():
    snapshot = {name: getattr(settings, name) for name in CLAUDE_SETTING_NAMES}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


# ---------- tests ----------


@pytest.mark.asyncio
async def test_claude_direct_send():
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "direct-ok"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20

    with patch("mascarade.router.providers.claude.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        provider = ClaudeProvider()
        response = await provider.send([{"role": "user", "content": "hello"}])

    assert provider.is_configured is True
    assert response.content == "direct-ok"
    assert response.provider == "claude"
    assert response.usage["input_tokens"] == 10
    assert response.usage["output_tokens"] == 20


@pytest.mark.asyncio
async def test_claude_proxy_send():
    """With litellm migration, proxy mode is handled by litellm config, not by provider."""
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "proxy-ok"
    mock_response.usage.prompt_tokens = 5
    mock_response.usage.completion_tokens = 15

    with patch("mascarade.router.providers.claude.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        provider = ClaudeProvider()
        response = await provider.send([{"role": "user", "content": "hello"}])

    assert response.content == "proxy-ok"
    assert response.usage["input_tokens"] == 5
    assert response.usage["output_tokens"] == 15


@pytest.mark.asyncio
async def test_claude_stream_direct():
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105

    async def fake_stream(*args, **kwargs):
        for text in ["chunk1", "chunk2"]:
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
            )

    with patch("mascarade.router.providers.claude.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=fake_stream())
        provider = ClaudeProvider()
        chunks = []
        async for chunk in provider.stream([{"role": "user", "content": "hi"}]):
            chunks.append(chunk)

    assert chunks == ["chunk1", "chunk2"]


@pytest.mark.asyncio
async def test_claude_stream_proxy():
    """With litellm migration, proxy streaming is the same code path."""
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105

    async def fake_stream(*args, **kwargs):
        for text in ["a", "b"]:
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
            )

    with patch("mascarade.router.providers.claude.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=fake_stream())
        provider = ClaudeProvider()
        chunks = []
        async for chunk in provider.stream([{"role": "user", "content": "hi"}]):
            chunks.append(chunk)

    assert chunks == ["a", "b"]


def test_claude_available_models():
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105
    with patch("mascarade.router.providers.claude.litellm", new=MagicMock()):
        provider = ClaudeProvider()
        models = provider.available_models()
    assert isinstance(models, list)
    assert any("claude" in m for m in models)


def test_claude_not_configured_when_no_key():
    settings.anthropic_api_key = ""
    with patch("mascarade.router.providers.claude.litellm", new=MagicMock()):
        provider = ClaudeProvider()
        assert provider.is_configured is False


@pytest.mark.asyncio
async def test_claude_send_with_system_prompt():
    settings.anthropic_api_key = "sk-ant-test-key-123456789"  # noqa: S105

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "direct-ok"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20

    with patch("mascarade.router.providers.claude.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        provider = ClaudeProvider()
        response = await provider.send(
            [{"role": "user", "content": "hi"}],
            system="You are helpful.",
        )
    assert response.content == "direct-ok"
