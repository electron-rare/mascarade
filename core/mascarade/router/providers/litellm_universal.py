"""LiteLLM Universal Provider — SDK-based adapter for all litellm-supported models.

Unlike the HTTP-proxy-based LiteLLMProvider, this provider calls litellm.acompletion()
directly, supporting 100+ LLM providers without needing a running proxy server.

When enabled as a fallback, it picks up any model request that no specific provider handles.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from mascarade.config import settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

logger = logging.getLogger("mascarade.providers.litellm_universal")

# Lazy import — litellm is optional
_litellm: Any = None
_litellm_available: bool | None = None


def _ensure_litellm() -> Any:
    """Import litellm on first use, caching the result."""
    global _litellm, _litellm_available  # noqa: PLW0603
    if _litellm_available is None:
        try:
            import litellm

            _litellm = litellm
            _litellm_available = True
            # Suppress litellm's own verbose logging unless DEBUG
            litellm.suppress_debug_info = True
        except ImportError:
            _litellm_available = False
            logger.info("litellm package not installed — LiteLLMUniversalProvider disabled")
    return _litellm


# Map Mascarade provider names to litellm model prefixes
_PROVIDER_PREFIX_MAP: dict[str, str] = {
    "anthropic": "anthropic/",
    "claude": "anthropic/",
    "openai": "openai/",
    "mistral": "mistral/",
    "google": "gemini/",
    "gemini": "gemini/",
    "bedrock": "bedrock/",
    "cohere": "cohere/",
    "huggingface": "huggingface/",
    "ollama": "ollama/",
    "groq": "groq/",
    "together": "together_ai/",
    "fireworks": "fireworks_ai/",
    "deepseek": "deepseek/",
    "perplexity": "perplexity/",
    "azure": "azure/",
}

_retry = make_retry()


class LiteLLMUniversalProvider(LLMProvider):
    """Universal LLM provider using litellm SDK for direct model calls.

    Supports all litellm model formats:
    - "gpt-4o" (auto-detected as OpenAI)
    - "claude-3-5-sonnet-20241022" (auto-detected as Anthropic)
    - "mistral/mistral-large-latest" (explicit prefix)
    - "bedrock/anthropic.claude-v2" (explicit prefix)
    - etc.

    Cost tracking via litellm.completion_cost() when available.
    """

    name = "litellm-universal"
    default_model = "gpt-4o"
    cost_per_million = (0.0, 0.0)  # Dynamic — tracked via litellm.completion_cost
    speed_rank = 5  # Low priority — fallback provider
    quality_rank = 1  # Low priority — specific providers preferred

    def __init__(self) -> None:
        self.default_model = settings.litellm_universal_default_model

    @property
    def is_configured(self) -> bool:
        if not settings.litellm_universal_enabled:
            return False
        return _ensure_litellm() is not None

    @staticmethod
    def resolve_model(model: str, provider_hint: str | None = None) -> str:
        """Resolve a model name to a litellm-compatible model string.

        If the model already has a provider prefix (contains '/'), return as-is.
        If a provider_hint is given and maps to a known prefix, prepend it.
        Otherwise return the raw model name — litellm can auto-detect many models.
        """
        if "/" in model:
            return model
        if provider_hint and provider_hint.lower() in _PROVIDER_PREFIX_MAP:
            return f"{_PROVIDER_PREFIX_MAP[provider_hint.lower()]}{model}"
        return model

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
        litellm = _ensure_litellm()
        if litellm is None:
            raise RuntimeError("litellm package is not installed")

        model = self.resolve_model(model or self.default_model)
        chat_messages = build_chat_messages(messages, system)

        response = await litellm.acompletion(
            model=model,
            messages=chat_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choices = response.choices
        if not choices:
            raise RuntimeError(f"litellm returned empty choices for model {model}")

        content = choices[0].message.content or ""
        usage_data = response.usage
        usage = {
            "input_tokens": getattr(usage_data, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage_data, "completion_tokens", 0) or 0,
        }

        # Track cost via litellm's built-in cost calculation
        cost = self._track_cost(response, model)
        if cost > 0:
            usage["estimated_cost_usd"] = cost

        return LLMResponse(
            content=content,
            model=model,
            provider=self.name,
            usage=usage,
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
        litellm = _ensure_litellm()
        if litellm is None:
            raise RuntimeError("litellm package is not installed")

        model = self.resolve_model(model or self.default_model)
        chat_messages = build_chat_messages(messages, system)

        response = await litellm.acompletion(
            model=model,
            messages=chat_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in response:
            choices = chunk.choices
            if not choices:
                continue
            delta = choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content

    def available_models(self) -> list[str]:
        """Return a representative set of commonly available litellm models."""
        litellm = _ensure_litellm()
        if litellm is None:
            return []
        # litellm supports 100+ models; return the most common ones
        try:
            # litellm.model_list or litellm.models_by_provider if available
            models = list(getattr(litellm, "model_cost", {}).keys())
            if models:
                return sorted(models)[:50]  # Cap to avoid huge lists
        except Exception:
            pass
        return [self.default_model]

    @staticmethod
    def _track_cost(response: Any, model: str) -> float:
        """Attempt to compute cost via litellm.completion_cost()."""
        litellm = _ensure_litellm()
        if litellm is None:
            return 0.0
        try:
            return float(litellm.completion_cost(completion_response=response))
        except Exception:
            logger.debug("Could not compute cost for model %s", model, exc_info=True)
            return 0.0
