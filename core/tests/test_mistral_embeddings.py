"""Tests for Mistral Embeddings Provider."""

from unittest.mock import MagicMock, patch

import pytest

from mascarade.router.providers.mistral_embeddings import MistralEmbeddingsProvider


@pytest.mark.asyncio
async def test_mistral_embeddings_initialization():
    """Test Mistral Embeddings provider initialization."""
    with patch(
        "mascarade.router.providers.mistral_embeddings.MISTRAL_EMBEDDINGS_AVAILABLE",
        True,
    ), patch(
        "mascarade.router.providers.mistral_embeddings.MistralClient"
    ) as mock_client:
        MistralEmbeddingsProvider(api_key="test-key")
        mock_client.assert_called_once_with(api_key="test-key")


@pytest.mark.asyncio
async def test_mistral_embeddings_embed():
    """Test Mistral embeddings generation."""
    with patch(
        "mascarade.router.providers.mistral_embeddings.MISTRAL_EMBEDDINGS_AVAILABLE",
        True,
    ), patch(
        "mascarade.router.providers.mistral_embeddings.MistralClient"
    ) as mock_client:
        # Setup mock response
        mock_data1 = MagicMock()
        mock_data1.embedding = [0.1, 0.2, 0.3]

        mock_data2 = MagicMock()
        mock_data2.embedding = [0.4, 0.5, 0.6]

        mock_response = MagicMock()
        mock_response.data = [mock_data1, mock_data2]

        mock_client.return_value.embeddings.return_value = mock_response

        provider = MistralEmbeddingsProvider(api_key="test-key")

        # Test embed
        texts = ["text1", "text2"]
        embeddings = await provider.embed(texts)

        # Verify
        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]


@pytest.mark.asyncio
async def test_mistral_embeddings_query():
    """Test Mistral embeddings for single query."""
    with patch(
        "mascarade.router.providers.mistral_embeddings.MISTRAL_EMBEDDINGS_AVAILABLE",
        True,
    ), patch(
        "mascarade.router.providers.mistral_embeddings.MistralClient"
    ) as mock_client:
        # Setup mock response
        mock_data = MagicMock()
        mock_data.embedding = [0.1, 0.2, 0.3]

        mock_response = MagicMock()
        mock_response.data = [mock_data]

        mock_client.return_value.embeddings.return_value = mock_response

        provider = MistralEmbeddingsProvider(api_key="test-key")

        # Test embed_query
        embedding = await provider.embed_query("test query")

        # Verify
        assert embedding == [0.1, 0.2, 0.3]


def test_mistral_embeddings_models():
    """Test available embedding models."""
    with patch(
        "mascarade.router.providers.mistral_embeddings.MISTRAL_EMBEDDINGS_AVAILABLE",
        True,
    ), patch("mascarade.router.providers.mistral_embeddings.MistralClient"):
        provider = MistralEmbeddingsProvider(api_key="test-key")
        models = provider.available_models()

        assert models == ["mistral-embed"]


def test_mistral_embeddings_without_client():
    """Test when Mistral client is not available."""
    with patch(
        "mascarade.router.providers.mistral_embeddings.MISTRAL_EMBEDDINGS_AVAILABLE",
        False,
    ):
        with pytest.raises(
            RuntimeError, match="Mistral embeddings client not available"
        ):
            MistralEmbeddingsProvider(api_key="test-key")
