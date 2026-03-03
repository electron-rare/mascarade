"""Adaptateur Anthropic Claude."""

from __future__ import annotations

from typing import AsyncIterator

import anthropic

from mascarade.config import settings
from mascarade.router.providers.base import LLMProvider, LLMResponse


class ClaudeProvider(LLMProvider):
    name = "claude"
    default_model = "claude-sonnet-4-6"
    cost_per_million = (3.0, 15.0)
    speed_rank = 2
    quality_rank = 3

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    @property
    def is_configured(self) -> bool:
        return bool(settings.anthropic_api_key)

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
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)
        return LLMResponse(
            content=response.content[0].text,
            model=model,
            provider=self.name,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
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
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    def available_models(self) -> list[str]:
        return [
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-6",
        ]
