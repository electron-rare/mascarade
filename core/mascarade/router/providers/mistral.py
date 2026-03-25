"""Adaptateur Mistral AI (via litellm)."""

from __future__ import annotations

from collections.abc import AsyncIterator

try:
    import litellm
except ImportError:
    litellm = None  # type: ignore[assignment]

from mascarade.config import is_secret_configured, settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

_retry = make_retry(ConnectionError, TimeoutError)


class MistralProvider(LLMProvider):
    name = "mistral"
    default_model = "mistral-large-latest"
    cost_per_million = (2.0, 6.0)
    speed_rank = 1
    quality_rank = 1

    @property
    def is_configured(self) -> bool:
        if litellm is None:
            return False
        return is_secret_configured(settings.mistral_api_key)

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
        if litellm is None:
            raise RuntimeError("litellm is not installed. Install with: pip install litellm")
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        kwargs: dict = {
            "model": f"mistral/{model}",
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format

        response = await litellm.acompletion(**kwargs)
        if not response.choices:
            raise RuntimeError(f"Mistral returned empty choices for model {model}")
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=model,
            provider=self.name,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": (response.usage.completion_tokens if response.usage else 0),
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
        if litellm is None:
            raise RuntimeError("litellm is not installed. Install with: pip install litellm")
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        response = await litellm.acompletion(
            model=f"mistral/{model}",
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
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
        return ["mistral-large-latest", "mistral-small-latest", "codestral-latest"]
