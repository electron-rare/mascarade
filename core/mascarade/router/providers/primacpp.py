"""Adaptateur Prima.cpp — inference LLM distribuee sur cluster heterogene.

Prima.cpp est un fork de llama.cpp qui distribue l'inference sur plusieurs
machines via une topologie en anneau (ring) et ZeroMQ. Il permet de faire
tourner des modeles 70B+ sur un cluster de machines domestiques.

Architecture:
    mascarade Router → PrimaCppProvider → prima.cpp HTTP API → ring cluster

Le provider detecte automatiquement si prima.cpp est disponible et quels
modeles sont charges dans le cluster distribue.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

from mascarade.config import settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

logger = logging.getLogger("mascarade.providers.primacpp")

_retry = make_retry(httpx.ConnectError, httpx.TimeoutException)

# Default prima.cpp server endpoint (OpenAI-compatible)
_DEFAULT_PRIMACPP_URL = "http://localhost:8088"


class PrimaCppProvider(LLMProvider):
    """Provider pour inference distribuee via prima.cpp.

    Prima.cpp expose une API compatible OpenAI sur le noeud coordinateur.
    Les requetes sont automatiquement distribuees sur le ring cluster.

    Configuration via env:
        PRIMACPP_URL: URL du coordinateur prima.cpp (default: http://localhost:8088)
        PRIMACPP_ENABLED: activer le provider (default: false)
    """

    name = "primacpp"

    def __init__(self) -> None:
        self._base_url = getattr(settings, "primacpp_url", _DEFAULT_PRIMACPP_URL)
        self._enabled = getattr(settings, "primacpp_enabled", False)
        self._timeout = getattr(settings, "primacpp_timeout_seconds", 300.0)
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout, connect=10.0),
            )
        return self._client

    @property
    def is_configured(self) -> bool:
        return self._enabled

    @_retry
    async def send(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMResponse:
        """Envoie une requete au cluster prima.cpp distribue.

        Le modele tourne sur le ring cluster — la latence est plus elevee
        qu'Ollama local mais permet des modeles 70B+ impossibles sur une
        seule machine.
        """
        messages = build_chat_messages(prompt, system=system)
        client = self._get_client()

        payload = {
            "model": model or "default",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        logger.info(
            "prima.cpp send: model=%s, prompt_len=%d",
            model,
            len(prompt),
        )

        response = await client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=model or data.get("model", "primacpp"),
            provider=self.name,
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        )

    async def stream(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream depuis le cluster prima.cpp distribue."""
        messages = build_chat_messages(prompt, system=system)
        client = self._get_client()

        payload = {
            "model": model or "default",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with client.stream(
            "POST", "/v1/chat/completions", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:]
                if chunk == "[DONE]":
                    break
                try:
                    import json
                    data = json.loads(chunk)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except Exception:
                    continue

    def available_models(self) -> list[str]:
        """Retourne les modeles disponibles sur le cluster.

        En mode synchrone, retourne une liste statique.
        Les modeles reels sont decouverts via /v1/models au runtime.
        """
        # TODO: query prima.cpp /v1/models endpoint
        return []

    async def discover_models(self) -> list[str]:
        """Decouvre dynamiquement les modeles charges dans le cluster."""
        try:
            client = self._get_client()
            response = await client.get("/v1/models")
            if response.status_code == 200:
                data = response.json()
                models = [m.get("id", "") for m in data.get("data", [])]
                logger.info("prima.cpp cluster models: %s", models)
                return models
        except Exception:
            logger.debug("prima.cpp not reachable for model discovery")
        return []

    async def cluster_status(self) -> dict:
        """Retourne l'etat du cluster prima.cpp (noeuds, ring, memoire)."""
        try:
            client = self._get_client()
            response = await client.get("/health")
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return {"status": "unreachable", "nodes": 0}
