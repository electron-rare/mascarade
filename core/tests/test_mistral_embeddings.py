"""Tests for Mistral Embeddings Provider (litellm-based)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.router.providers.mistral_embeddings import MistralEmbeddingsProvider


@pytest.mark.asyncio
async def test_mistral_embeddings_initialization():
    """Test Mistral Embeddings provider initialization."""
    with patch("mascarade.router.providers.mistral_embeddings.litellm", new=MagicMock()):
        provider = MistralEmbeddingsProvider(api_key="test-key")
        assert provider._api_key == "test-key"


@pytest.mark.asyncio
async def test_mistral_embeddings_embed():
    """Test Mistral embeddings generation."""
    mock_response = MagicMock()
    mock_response.data = [
        {"embedding": [0.1, 0.2, 0.3]},
        {"embedding": [0.4, 0.5, 0.6]},
    ]

    with patch("mascarade.router.providers.mistral_embeddings.litellm") as mock_litellm:
        mock_litellm.aembedding = AsyncMock(return_value=mock_response)
        provider = MistralEmbeddingsProvider(api_key="test-key")

        texts = ["text1", "text2"]
        embeddings = await provider.embed(texts)

    assert len(embeddings) == 2
    assert embeddings[0] == [0.1, 0.2, 0.3]
    assert embeddings[1] == [0.4, 0.5, 0.6]

    # Verify litellm was called with correct model prefix
    mock_litellm.aembedding.assert_awaited_once()
    call_kwargs = mock_litellm.aembedding.call_args
    assert call_kwargs.kwargs["model"] == "mistral/mistral-embed"


@pytest.mark.asyncio
async def test_mistral_embeddings_query():
    """Test Mistral embeddings for single query."""
    mock_response = MagicMock()
    mock_response.data = [{"embedding": [0.1, 0.2, 0.3]}]

    with patch("mascarade.router.providers.mistral_embeddings.litellm") as mock_litellm:
        mock_litellm.aembedding = AsyncMock(return_value=mock_response)
        provider = MistralEmbeddingsProvider(api_key="test-key")

        embedding = await provider.embed_query("test query")

    assert embedding == [0.1, 0.2, 0.3]


def test_mistral_embeddings_models():
    """Test available embedding models."""
    with patch("mascarade.router.providers.mistral_embeddings.litellm", new=MagicMock()):
        provider = MistralEmbeddingsProvider(api_key="test-key")
        models = provider.available_models()

    assert models == ["mistral-embed"]


@pytest.mark.asyncio
async def test_mistral_embeddings_without_client():
    """Test when litellm is not available."""
    with patch("mascarade.router.providers.mistral_embeddings.litellm", None):
        provider = MistralEmbeddingsProvider(api_key="test-key")
        # Should not raise on init, but should raise on embed
        with pytest.raises(RuntimeError, match="litellm is not installed"):
            await provider.embed(["test"])
