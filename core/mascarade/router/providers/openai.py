"""Adaptateur OpenAI."""

from __future__ import annotations

from collections.abc import AsyncIterator

import openai

from mascarade.config import is_secret_configured, settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

_retry = make_retry(
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
)


class OpenAIProvider(LLMProvider):
    name = "openai"
    default_model = "gpt-4o"
    cost_per_million = (2.5, 10.0)
    speed_rank = 1
    quality_rank = 2

    def __init__(self) -> None:
        self._proxy_enabled = bool(
            settings.litellm_proxy_enabled
            and settings.litellm_base_url.strip()
            and is_secret_configured(settings.litellm_master_key)
        )
        self._client = openai.AsyncOpenAI(
            api_key=(
                settings.litellm_master_key
                if self._proxy_enabled
                else settings.openai_api_key
            ),
            base_url=(settings.litellm_base_url if self._proxy_enabled else None),
            timeout=30.0,
        )

    @property
    def is_configured(self) -> bool:
        if self._proxy_enabled:
            return bool(
                settings.litellm_base_url.strip()
                and is_secret_configured(settings.litellm_master_key)
            )
        return is_secret_configured(settings.openai_api_key)

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

        response = await self._client.chat.completions.create(
            model=model,
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if not response.choices:
            raise RuntimeError(f"OpenAI returned empty choices for model {model}")
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=model,
            provider=self.name,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": (
                    response.usage.completion_tokens if response.usage else 0
                ),
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

        stream = await self._client.chat.completions.create(
            model=model,
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def available_models(self) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini", "o1", "o3-mini"]
