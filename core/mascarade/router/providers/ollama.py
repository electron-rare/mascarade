"""Adaptateur Ollama — modèles LLM locaux."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from mascarade.config import settings
from mascarade.router.providers.base import LLMProvider, LLMResponse, make_retry

logger = logging.getLogger("mascarade.providers.ollama")

_retry = make_retry(httpx.ConnectError, httpx.TimeoutException)


class OllamaProvider(LLMProvider):
    name = "ollama"
    default_model = "qwen3.5:9b"
    cost_per_million = (0.0, 0.0)
    speed_rank = 1
    quality_rank = 1

    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=180.0,
        )

    @property
    def is_configured(self) -> bool:
        try:
            with httpx.Client(base_url=self._base_url, timeout=3.0) as client:
                resp = client.get("/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    @_retry
    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = model or self.default_model
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        response = await self._client.post(
            "/api/chat",
            json={
                "model": model,
                "messages": chat_messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
        )
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            model=model,
            provider=self.name,
            usage={
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
            },
        )

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        model = model or self.default_model
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        async with self._client.stream(
            "POST",
            "/api/chat",
            json={
                "model": model,
                "messages": chat_messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue

    def available_models(self) -> list[str]:
        try:
            with httpx.Client(base_url=self._base_url, timeout=5.0) as client:
                resp = client.get("/api/tags")
                resp.raise_for_status()
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            logger.warning("Impossible de lister les modèles Ollama")
            return [self.default_model]
