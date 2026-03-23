"""Adaptateur LiteLLM — proxy OpenAI-compatible pour multi-provider."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator

import httpx

from mascarade.config import is_secret_configured, secret_value, settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

logger = logging.getLogger("mascarade.providers.litellm")

_retry = make_retry(httpx.ConnectError, httpx.TimeoutException)


class LiteLLMProvider(LLMProvider):
    """Provider targeting a LiteLLM proxy (OpenAI-compatible API)."""

    name = "litellm"
    default_model = "gpt-4o"
    cost_per_million = (0.0, 0.0)  # LiteLLM tracks costs internally
    speed_rank = 2
    quality_rank = 2

    def __init__(self) -> None:
        self._base_url = settings.litellm_base_url.rstrip("/")
        self._timeout = settings.litellm_timeout_seconds
        self._api_key = secret_value(settings.litellm_master_key)
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            headers=self._make_headers(),
        )
        self._models_cache: list[str] | None = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 60.0

    def _make_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    @property
    def is_configured(self) -> bool:
        if not settings.litellm_enabled:
            return False
        if not self._base_url:
            return False
        return is_secret_configured(settings.litellm_master_key)

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
        chat_messages = build_chat_messages(messages, system)

        payload = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            response = await self._client.post(
                "/chat/completions",
                json=payload,
            )
        except httpx.ReadTimeout:
            raise RuntimeError(
                f"LiteLLM proxy timeout after {int(self._timeout)}s "
                f"on model={model}. "
                f"Increase LITELLM_TIMEOUT_SECONDS if the model needs more time."
            ) from None

        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"LiteLLM returned empty choices for model {model}")

        choice = choices[0]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice.get("message", {}).get("content", ""),
            model=model,
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

        payload = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        async with self._client.stream(
            "POST",
            "/chat/completions",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                # SSE format: "data: {...}" or "data: [DONE]"
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue

    def available_models(self) -> list[str]:
        """Query LiteLLM /models endpoint (with cache)."""
        current_time = time.time()
        if (
            self._models_cache is not None
            and (current_time - self._cache_timestamp) < self._cache_ttl
        ):
            return self._models_cache

        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=5.0,
                headers=self._make_headers(),
            ) as client:
                resp = client.get("/models")
                resp.raise_for_status()
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]

                self._models_cache = models
                self._cache_timestamp = current_time
                return models
        except Exception:
            logger.warning("Cannot list LiteLLM models at %s", self._base_url)
            if self._models_cache is not None:
                return self._models_cache
            return [self.default_model]
