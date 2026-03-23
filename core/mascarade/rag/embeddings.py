"""Embedding generation for RAG — supports multiple providers."""

from __future__ import annotations

import logging

import httpx

from mascarade.config import is_secret_configured, secret_value, settings

logger = logging.getLogger("mascarade.rag.embeddings")

# Dimension lookup for common embedding models
_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "mistral-embed": 1024,
}


class EmbeddingProvider:
    """Generate embeddings via mascarade's configured providers.

    Tries providers in order: OpenAI, Mistral, HuggingFace, Qdrant fastembed.
    """

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed(
        self,
        texts: list[str],
        model: str = "text-embedding-3-small",
    ) -> list[list[float]]:
        """Generate embeddings. Tries: OpenAI, Mistral, HuggingFace, local Qdrant fastembed."""
        if not texts:
            return []

        # Try OpenAI
        if is_secret_configured(settings.openai_api_key) and model.startswith(
            "text-embedding"
        ):
            try:
                return await self._embed_openai(texts, model)
            except Exception as exc:
                logger.warning("OpenAI embedding failed, trying next provider: %s", exc)

        # Try Mistral
        if is_secret_configured(settings.mistral_api_key):
            try:
                return await self._embed_mistral(texts)
            except Exception as exc:
                logger.warning(
                    "Mistral embedding failed, trying next provider: %s", exc
                )

        # Try HuggingFace
        if is_secret_configured(settings.huggingface_api_key):
            try:
                return await self._embed_huggingface(texts)
            except Exception as exc:
                logger.warning(
                    "HuggingFace embedding failed, trying next provider: %s", exc
                )

        # Fallback: Qdrant fastembed
        return await self._embed_qdrant_fastembed(texts)

    async def embed_query(
        self, query: str, model: str = "text-embedding-3-small"
    ) -> list[float]:
        """Embed a single query string."""
        results = await self.embed([query], model=model)
        return results[0]

    def dimension_for_model(self, model: str = "text-embedding-3-small") -> int:
        """Return the expected dimension for a given model."""
        return _MODEL_DIMENSIONS.get(model, 1536)

    # ------------------------------------------------------------------
    # Provider backends
    # ------------------------------------------------------------------

    async def _embed_openai(self, texts: list[str], model: str) -> list[list[float]]:
        client = await self._get_client()
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {secret_value(settings.openai_api_key)}",
                "Content-Type": "application/json",
            },
            json={"input": texts, "model": model},
        )
        resp.raise_for_status()
        data = resp.json()
        # Sort by index to guarantee order
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]

    async def _embed_mistral(self, texts: list[str]) -> list[list[float]]:
        client = await self._get_client()
        resp = await client.post(
            f"{settings.mistral_api_base}/embeddings",
            headers={
                "Authorization": f"Bearer {secret_value(settings.mistral_api_key)}",
                "Content-Type": "application/json",
            },
            json={"input": texts, "model": "mistral-embed"},
        )
        resp.raise_for_status()
        data = resp.json()
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]

    async def _embed_huggingface(self, texts: list[str]) -> list[list[float]]:
        client = await self._get_client()
        api_key = secret_value(settings.huggingface_api_key)
        resp = await client.post(
            "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"inputs": texts, "options": {"wait_for_model": True}},
        )
        resp.raise_for_status()
        return resp.json()

    async def _embed_qdrant_fastembed(self, texts: list[str]) -> list[list[float]]:
        """Use Qdrant's built-in fastembed endpoint as last-resort fallback."""
        client = await self._get_client()
        # Qdrant exposes POST /embeddings when fastembed is enabled
        resp = await client.post(
            f"{settings.qdrant_url}/embeddings",
            json={"model": "fast-all-MiniLM-L6-v2", "inputs": texts},
        )
        if resp.status_code == 404:
            raise RuntimeError(
                "No embedding provider available. Configure an API key for "
                "OpenAI, Mistral, or HuggingFace, or enable fastembed in Qdrant."
            )
        resp.raise_for_status()
        data = resp.json()
        return data.get("embeddings", data.get("data", []))
