"""Mistral AI Studio Provider - Integration with Mistral's cloud platform (via litellm)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

try:
    import litellm
except ImportError:
    litellm = None  # type: ignore[assignment]

from mascarade.router.providers.base import LLMProvider, LLMResponse, build_chat_messages

logger = logging.getLogger("mascarade.mistral_studio")


class MistralStudioProvider(LLMProvider):
    """Provider for Mistral AI Studio cloud services."""

    name: str = "mistral-studio"
    default_model: str = "mistral-large-latest"

    # Cost per 1M tokens (input, output) for Mistral Studio
    cost_per_million: tuple[float, float] = (0.25, 0.25)  # USD

    # Performance characteristics
    speed_rank: int = 2  # Fast cloud response
    quality_rank: int = 4  # High quality

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key
        if litellm is None:
            logger.warning("litellm is not installed. MistralStudioProvider will be unavailable.")

    @property
    def is_configured(self) -> bool:
        return litellm is not None and bool(self._api_key)

    async def send(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send request to Mistral Studio API."""
        if litellm is None:
            raise RuntimeError("litellm is not installed. Install with: pip install litellm")
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        response = await litellm.acompletion(
            model=f"mistral/{model}",
            messages=chat_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self._api_key,
        )
        if not response.choices:
            raise RuntimeError(f"Mistral Studio returned empty choices for model {model}")
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model or model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": (response.usage.completion_tokens if response.usage else 0),
                "total_tokens": response.usage.total_tokens if response.usage else 0,
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
        """Stream response from Mistral Studio."""
        if litellm is None:
            raise RuntimeError("litellm is not installed. Install with: pip install litellm")
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        response = await litellm.acompletion(
            model=f"mistral/{model}",
            messages=chat_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self._api_key,
            stream=True,
        )
        async for chunk in response:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            content = getattr(delta, "content", None)
            if content:
                yield content

    def available_models(self) -> list[str]:
        """Available Mistral Studio models."""
        return [
            "mistral-tiny",
            "mistral-small",
            "mistral-medium",
            "mistral-large-latest",
        ]

    async def close(self) -> None:
        """Clean up resources."""
        pass
