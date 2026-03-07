"""Adaptateur Ollama — modeles LLM locaux."""

from __future__ import annotations

import json
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
        if not self._base_url:
            return False
        if settings.ollama_enabled:
            return True
        return self._base_url != "http://ollama:11434"

    @_retry
    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        payload = {
            "model": model,
            "messages": chat_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if response_format is not None:
            if response_format.get("type") == "json_object":
                payload["format"] = "json"
            else:
                payload["format"] = response_format

        response = await self._client.post(
            "/api/chat",
            json=payload,
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
        chat_messages = build_chat_messages(messages, system)

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
            logger.warning("Cannot list Ollama models at %s", self._base_url)
            return [self.default_model]
