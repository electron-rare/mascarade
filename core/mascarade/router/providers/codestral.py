"""Codestral provider — Mistral's code-specialized model with FIM support."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

from mascarade.config import is_secret_configured, secret_value, settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

logger = logging.getLogger("mascarade.providers.codestral")

_retry = make_retry(httpx.TimeoutException, httpx.TransportError)

# Codestral endpoints
_CODESTRAL_CHAT_URL = "https://codestral.mistral.ai/v1/chat/completions"
_CODESTRAL_FIM_URL = "https://codestral.mistral.ai/v1/fim/completions"


class CodestralProvider(LLMProvider):
    """Mistral Codestral — code-specialized LLM with Fill-in-the-Middle."""

    name = "codestral"
    default_model = "codestral-latest"
    cost_per_million = (0.3, 0.9)  # USD per 1M tokens
    speed_rank = 1
    quality_rank = 3  # High quality for code tasks

    def __init__(self) -> None:
        api_key = secret_value(getattr(settings, "codestral_api_key", "") or "")
        self._api_key = api_key.strip()
        timeout = getattr(settings, "codestral_timeout_seconds", 120.0)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )

    @property
    def is_configured(self) -> bool:
        return is_secret_configured(self._api_key)

    def available_models(self) -> list[str]:
        return ["codestral-latest", "codestral-2501"]

    @_retry
    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a chat completion request to Codestral."""
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        payload: dict = {
            "model": model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        resp = await self._client.post(_CODESTRAL_CHAT_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"Codestral returned empty choices for model {model}")

        content = choices[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=data.get("model", model),
            provider=self.name,
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens from Codestral."""
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        payload: dict = {
            "model": model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with self._client.stream("POST", _CODESTRAL_CHAT_URL, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:]
                if chunk.strip() == "[DONE]":
                    break
                import json

                data = json.loads(chunk)
                delta = data.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content

    async def fill_in_middle(
        self,
        prompt: str,
        suffix: str = "",
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        stop: list[str] | None = None,
    ) -> str:
        """Codestral FIM (Fill-in-the-Middle) completion for code infilling.

        Args:
            prompt: Code before the cursor position.
            suffix: Code after the cursor position.
            model: Model override.
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens: Maximum tokens to generate.
            stop: Stop sequences.

        Returns:
            The generated code to fill between prompt and suffix.
        """
        model = model or self.default_model
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "suffix": suffix,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stop:
            payload["stop"] = stop

        resp = await self._client.post(_CODESTRAL_FIM_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("text", "") or choices[0].get("message", {}).get("content", "")
