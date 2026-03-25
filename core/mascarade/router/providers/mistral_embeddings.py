"""Mistral Embeddings Provider - Vector embeddings for semantic search (via litellm)."""

from __future__ import annotations

import logging

try:
    import litellm
except ImportError:
    litellm = None  # type: ignore[assignment]

logger = logging.getLogger("mascarade.mistral_embeddings")


class MistralEmbeddingsProvider:
    """Provider for Mistral embeddings service."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key
        if litellm is None:
            logger.warning(
                "litellm is not installed. MistralEmbeddingsProvider will be unavailable."
            )

    async def embed(
        self,
        texts: list[str],
        model: str = "mistral-embed",
        dimensions: int = 1024,
    ) -> list[list[float]]:
        """Generate embeddings for texts."""
        if litellm is None:
            raise RuntimeError("litellm is not installed. Install with: pip install litellm")
        response = await litellm.aembedding(
            model=f"mistral/{model}",
            input=texts,
            dimensions=dimensions,
            api_key=self._api_key,
        )
        return [data["embedding"] for data in response.data]

    async def embed_query(
        self,
        text: str,
        model: str = "mistral-embed",
        dimensions: int = 1024,
    ) -> list[float]:
        """Generate embedding for a single query."""
        embeddings = await self.embed([text], model=model, dimensions=dimensions)
        return embeddings[0]

    def available_models(self) -> list[str]:
        """Available embedding models."""
        return ["mistral-embed"]

    async def close(self) -> None:
        """Clean up resources."""
        pass
