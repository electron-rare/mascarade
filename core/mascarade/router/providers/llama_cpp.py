"""Adaptateur llama.cpp — serveur OpenAI-compatible local."""

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

logger = logging.getLogger("mascarade.providers.llama_cpp")

_retry = make_retry(httpx.ConnectError, httpx.TimeoutException)


class LlamaCppProvider(LLMProvider):
    name = "llama_cpp"
    default_model = "local"
    cost_per_million = (0.0, 0.0)
    speed_rank = 1
    quality_rank = 1

    def __init__(self) -> None:
        self._base_url = getattr(settings, "llama_cpp_base_url", "http://localhost:8081/v1").rstrip("/")
        self._enabled = getattr(settings, "llama_cpp_enabled", False)
        self._timeout = getattr(settings, "llama_cpp_timeout_seconds", 120.0)
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
        )

    @property
    def is_configured(self) -> bool:
        return self._enabled

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

        payload: dict = {
            "model": model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [{}])
        choice = choices[0] if choices else {}
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice.get("message", {}).get("content", ""),
            model=data.get("model", model),
            provider=self.name,
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
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
            "/chat/completions",
            json={
                "model": model,
                "messages": chat_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                chunk = line[6:]
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue

    def available_models(self) -> list[str]:
        try:
            with httpx.Client(base_url=self._base_url, timeout=5.0) as client:
                resp = client.get("/models")
                resp.raise_for_status()
                return [m["id"] for m in resp.json().get("data", [])]
        except Exception:
            return [self.default_model]
