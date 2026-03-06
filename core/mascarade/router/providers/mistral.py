"""Adaptateur Mistral AI."""

from __future__ import annotations

from collections.abc import AsyncIterator

from mistralai import Mistral

from mascarade.config import is_secret_configured, settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

_retry = make_retry()


class MistralProvider(LLMProvider):
    name = "mistral"
    default_model = "mistral-large-latest"
    cost_per_million = (2.0, 6.0)
    speed_rank = 1
    quality_rank = 1

    def __init__(self) -> None:
        self._client = Mistral(
            api_key=settings.mistral_api_key,
            timeout_ms=30_000,
        )

    @property
    def is_configured(self) -> bool:
        return is_secret_configured(settings.mistral_api_key)

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

        response = await self._client.chat.complete_async(
            model=model,
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content,
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

        response = await self._client.chat.stream_async(
            model=model,
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        async for event in response:
            if event.data.choices and event.data.choices[0].delta.content:
                yield event.data.choices[0].delta.content

    def available_models(self) -> list[str]:
        return ["mistral-large-latest", "mistral-small-latest", "codestral-latest"]
