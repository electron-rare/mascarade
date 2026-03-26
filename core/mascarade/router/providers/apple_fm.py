"""Apple Foundation Models — on-device 3B inference via Swift bridge."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator

import httpx

from mascarade.config import settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

logger = logging.getLogger("mascarade.providers.apple_fm")

_retry = make_retry(httpx.ConnectError, httpx.TimeoutException)


class AppleFMProvider(LLMProvider):
    """Provider for Apple Foundation Models — on-device 3B via Swift bridge.

    Connects to the afm-bridge Swift executable exposing an OpenAI-compatible API.
    Default endpoint: http://localhost:8090/v1

    Config env vars:
        AFM_ENABLED: bool — enable this provider (default False)
        AFM_BRIDGE_URL: str — bridge base URL (default http://localhost:8090)
        AFM_DEFAULT_MODEL: str — default model name (default apple-fm-3b)
        AFM_TIMEOUT_SECONDS: float — request timeout (default 60.0)
    """

    name = "apple_fm"
    default_model = "apple-fm-3b"
    cost_per_million = (0.0, 0.0)  # On-device — free
    speed_rank = 1
    quality_rank = 2

    def __init__(self) -> None:
        self._enabled: bool = getattr(settings, "afm_enabled", False)
        self._base_url: str = getattr(settings, "afm_bridge_url", "http://localhost:8090").rstrip(
            "/"
        )
        self.default_model = getattr(settings, "afm_default_model", "apple-fm-3b")
        self._timeout: float = getattr(settings, "afm_timeout_seconds", 60.0)
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
        )
        self._models_cache: list[str] | None = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 30.0

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

        try:
            response = await self._client.post(
                "/v1/chat/completions",
                json=payload,
            )
        except httpx.ReadTimeout:
            raise RuntimeError(
                f"AFM bridge timeout after {int(self._timeout)}s "
                f"on model={model} max_tokens={max_tokens}. "
                f"Increase AFM_TIMEOUT_SECONDS if the model needs more time."
            ) from None
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
            "/v1/chat/completions",
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
        """List available models from the bridge (with cache)."""
        current_time = time.time()
        if (
            self._models_cache is not None
            and (current_time - self._cache_timestamp) < self._cache_ttl
        ):
            return self._models_cache

        try:
            with httpx.Client(base_url=self._base_url, timeout=5.0) as client:
                resp = client.get("/v1/models")
                resp.raise_for_status()
                models = [m["id"] for m in resp.json().get("data", [])]

                self._models_cache = models
                self._cache_timestamp = current_time
                return models
        except Exception:
            logger.warning("Cannot list AFM models at %s", self._base_url)
            if self._models_cache is not None:
                return self._models_cache
            return [self.default_model]

    def is_model_available(self, model_name: str) -> bool:
        """Check if a specific model is available."""
        return model_name in self.available_models()
