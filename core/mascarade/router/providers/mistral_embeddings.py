"""Mistral Embeddings Provider - Vector embeddings for semantic search."""

from __future__ import annotations

import logging
from typing import List

try:
    from mistralai.client import MistralClient
    MISTRAL_EMBEDDINGS_AVAILABLE = True
except ImportError:
    MISTRAL_EMBEDDINGS_AVAILABLE = False
    MistralClient = object

logger = logging.getLogger("mascarade.mistral_embeddings")


class MistralEmbeddingsProvider:
    """Provider for Mistral embeddings service."""

    def __init__(self, api_key: str):
        if not MISTRAL_EMBEDDINGS_AVAILABLE:
            raise RuntimeError(
                "Mistral embeddings client not available. "
                "Install with: pip install mistralai"
            )

        self.client = MistralClient(api_key=api_key)
        logger.info("Mistral Embeddings provider initialized")

    async def embed(
        self,
        texts: List[str],
        model: str = "mistral-embed",
        dimensions: int = 1024,
    ) -> List[List[float]]:
        """Generate embeddings for texts."""
        response = self.client.embeddings(
            model=model,
            input=texts,
            dimensions=dimensions,
        )
        
        return [data.embedding for data in response.data]

    async def embed_query(
        self,
        text: str,
        model: str = "mistral-embed",
        dimensions: int = 1024,
    ) -> List[float]:
        """Generate embedding for a single query."""
        embeddings = await self.embed([text], model=model, dimensions=dimensions)
        return embeddings[0]

    def available_models(self) -> List[str]:
        """Available embedding models."""
        return ["mistral-embed"]

    async def close(self) -> None:
        """Clean up resources."""
        pass
