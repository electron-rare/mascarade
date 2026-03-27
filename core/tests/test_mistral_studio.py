"""Tests for Mistral Studio Provider (litellm-based)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.router.providers.base import LLMResponse
from mascarade.router.providers.mistral_studio import MistralStudioProvider


@pytest.mark.asyncio
async def test_mistral_studio_initialization():
    """Test Mistral Studio provider initialization."""
    with patch("mascarade.router.providers.mistral_studio.litellm", new=MagicMock()):
        provider = MistralStudioProvider(api_key="test-key")
        assert provider.name == "mistral-studio"
        assert provider.is_configured is True


@pytest.mark.asyncio
async def test_mistral_studio_not_configured_without_key():
    """Test provider is not configured without API key."""
    with patch("mascarade.router.providers.mistral_studio.litellm", new=MagicMock()):
        provider = MistralStudioProvider(api_key=None)
        assert provider.is_configured is False


@pytest.mark.asyncio
async def test_mistral_studio_send():
    """Test Mistral Studio send method."""
    mock_litellm = MagicMock()

    # Setup mock response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "test response"
    mock_response.model = "mistral-large-latest"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    mock_response.usage.total_tokens = 30

    mock_litellm.acompletion = AsyncMock(return_value=mock_response)

    with patch("mascarade.router.providers.mistral_studio.litellm", mock_litellm):
        provider = MistralStudioProvider(api_key="test-key")
        messages = [{"role": "user", "content": "test"}]
        response = await provider.send(messages)

    assert isinstance(response, LLMResponse)
    assert response.content == "test response"
    assert response.model == "mistral-large-latest"
    assert response.usage["total_tokens"] == 30

    # Verify litellm was called with correct model prefix
    mock_litellm.acompletion.assert_awaited_once()
    call_kwargs = mock_litellm.acompletion.call_args
    assert call_kwargs.kwargs["model"] == "mistral/mistral-large-latest"
    assert call_kwargs.kwargs["api_key"] == "test-key"


@pytest.mark.asyncio
async def test_mistral_studio_stream():
    """Test Mistral Studio stream method."""
    mock_litellm = MagicMock()

    # Setup mock async stream
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock()]
    mock_chunk1.choices[0].delta.content = "chunk1"

    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock()]
    mock_chunk2.choices[0].delta.content = "chunk2"

    async def fake_stream(*args, **kwargs):
        for chunk in [mock_chunk1, mock_chunk2]:
            yield chunk

    mock_litellm.acompletion = AsyncMock(return_value=fake_stream())

    with patch("mascarade.router.providers.mistral_studio.litellm", mock_litellm):
        provider = MistralStudioProvider(api_key="test-key")
        messages = [{"role": "user", "content": "test"}]
        chunks = []
        async for chunk in provider.stream(messages):
            chunks.append(chunk)

    assert chunks == ["chunk1", "chunk2"]


def test_mistral_studio_models():
    """Test available models."""
    with patch("mascarade.router.providers.mistral_studio.litellm", new=MagicMock()):
        provider = MistralStudioProvider(api_key="test-key")
        models = provider.available_models()

    assert "mistral-tiny" in models
    assert "mistral-small" in models
    assert "mistral-medium" in models
    assert "mistral-large-latest" in models


def test_mistral_studio_without_litellm():
    """Test when litellm is not available."""
    with patch("mascarade.router.providers.mistral_studio.litellm", None):
        provider = MistralStudioProvider(api_key="test-key")
        assert provider.is_configured is False


@pytest.mark.asyncio
async def test_mistral_studio_send_without_litellm():
    """Test send raises when litellm is not installed."""
    with patch("mascarade.router.providers.mistral_studio.litellm", None):
        provider = MistralStudioProvider(api_key="test-key")
        with pytest.raises(RuntimeError, match="litellm is not installed"):
            await provider.send([{"role": "user", "content": "test"}])
