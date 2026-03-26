"""Perplexity provider — sonar models with built-in web search."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

try:
    import litellm
except ImportError:
    litellm = None  # type: ignore[assignment]

from mascarade.config import is_secret_configured, secret_value, settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

logger = logging.getLogger("mascarade.providers.perplexity")

_retry = make_retry(ConnectionError, TimeoutError)

_MODELS = [
    "sonar",
    "sonar-pro",
    "sonar-reasoning",
    "sonar-reasoning-pro",
    "sonar-deep-research",
]

# USD per 1M tokens (input, output) — approximate
_COSTS: dict[str, tuple[float, float]] = {
    "sonar": (1.0, 1.0),
    "sonar-pro": (3.0, 15.0),
    "sonar-reasoning": (1.0, 5.0),
    "sonar-reasoning-pro": (2.0, 8.0),
    "sonar-deep-research": (2.0, 8.0),
}


class PerplexityProvider(LLMProvider):
    """Perplexity sonar — LLM with real-time web search built in."""

    name = "perplexity"
    default_model = "sonar"
    cost_per_million = _COSTS["sonar"]
    speed_rank = 2
    quality_rank = 3

    def __init__(self) -> None:
        self._api_key = secret_value(getattr(settings, "perplexity_api_key", "") or "").strip()
        self._base_url = getattr(settings, "perplexity_base_url", "https://api.perplexity.ai")

    @property
    def is_configured(self) -> bool:
        if litellm is None:
            return False
        return is_secret_configured(self._api_key)

    def available_models(self) -> list[str]:
        return _MODELS

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
        if litellm is None:
            raise RuntimeError("litellm is not installed")
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        kwargs: dict = {
            "model": f"perplexity/{model}",
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "api_key": self._api_key,
            "api_base": self._base_url,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await litellm.acompletion(**kwargs)
        if not response.choices:
            raise RuntimeError(f"Perplexity returned empty choices for model {model}")

        choice = response.choices[0]
        citations = getattr(response, "citations", None) or []

        return LLMResponse(
            content=choice.message.content or "",
            model=model,
            provider=self.name,
            usage={
                "input_tokens": (response.usage.prompt_tokens if response.usage else 0),
                "output_tokens": (response.usage.completion_tokens if response.usage else 0),
            },
            metadata={"citations": citations} if citations else {},
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
        if litellm is None:
            raise RuntimeError("litellm is not installed")
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        kwargs: dict = {
            "model": f"perplexity/{model}",
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "api_key": self._api_key,
            "api_base": self._base_url,
            "stream": True,
        }

        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
