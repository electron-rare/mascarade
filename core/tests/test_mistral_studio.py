"""Tests for Mistral Studio Provider."""

from unittest.mock import MagicMock, patch

import pytest

from mascarade.router.providers.base import LLMResponse
from mascarade.router.providers.mistral_studio import MistralStudioProvider


@pytest.mark.asyncio
async def test_mistral_studio_initialization():
    """Test Mistral Studio provider initialization."""
    with patch('mascarade.router.providers.mistral_studio.MISTRAL_STUDIO_AVAILABLE', True), \
         patch('mascarade.router.providers.mistral_studio.MistralClient') as mock_client:
        provider = MistralStudioProvider(api_key="test-key")
        mock_client.assert_called_once_with(api_key="test-key")
        assert provider.name == "mistral-studio"


@pytest.mark.asyncio
async def test_mistral_studio_send():
    """Test Mistral Studio send method."""
    # Create mock ChatMessage class
    mock_chat_message_class = MagicMock()

    with patch('mascarade.router.providers.mistral_studio.MISTRAL_STUDIO_AVAILABLE', True), \
         patch('mascarade.router.providers.mistral_studio.MistralClient') as mock_client, \
         patch('mascarade.router.providers.mistral_studio.ChatMessage', mock_chat_message_class):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "test response"
        mock_response.model = "mistral-large-latest"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        mock_client.return_value.chat.return_value = mock_response

        provider = MistralStudioProvider(api_key="test-key")

        # Test send
        messages = [{"role": "user", "content": "test"}]
        response = await provider.send(messages)

        # Verify
        assert isinstance(response, LLMResponse)
        assert response.content == "test response"
        assert response.model == "mistral-large-latest"
        assert response.usage["total_tokens"] == 30


@pytest.mark.asyncio
async def test_mistral_studio_stream():
    """Test Mistral Studio stream method."""
    # Create mock ChatMessage class
    mock_chat_message_class = MagicMock()

    with patch('mascarade.router.providers.mistral_studio.MISTRAL_STUDIO_AVAILABLE', True), \
         patch('mascarade.router.providers.mistral_studio.MistralClient') as mock_client, \
         patch('mascarade.router.providers.mistral_studio.ChatMessage', mock_chat_message_class):
        # Setup mock stream
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta = MagicMock()
        mock_chunk1.choices[0].delta.content = "chunk1"

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta = MagicMock()
        mock_chunk2.choices[0].delta.content = "chunk2"

        mock_client.return_value.chat_stream.return_value = [mock_chunk1, mock_chunk2]

        provider = MistralStudioProvider(api_key="test-key")

        # Test stream
        messages = [{"role": "user", "content": "test"}]
        chunks = []
        async for chunk in provider.stream(messages):
            chunks.append(chunk)

        # Verify
        assert chunks == ["chunk1", "chunk2"]


def test_mistral_studio_models():
    """Test available models."""
    with patch('mascarade.router.providers.mistral_studio.MISTRAL_STUDIO_AVAILABLE', True), \
         patch('mascarade.router.providers.mistral_studio.MistralClient'):
        provider = MistralStudioProvider(api_key="test-key")
        models = provider.available_models()

        assert "mistral-tiny" in models
        assert "mistral-small" in models
        assert "mistral-medium" in models
        assert "mistral-large-latest" in models


def test_mistral_studio_without_client():
    """Test when Mistral client is not available."""
    with patch('mascarade.router.providers.mistral_studio.MISTRAL_STUDIO_AVAILABLE', False):
        with pytest.raises(RuntimeError, match="Mistral Studio client not available"):
            MistralStudioProvider(api_key="test-key")
