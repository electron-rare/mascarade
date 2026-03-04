"""Adaptateur Hugging Face Inference (API OpenAI-compatible)."""

from __future__ import annotations

from typing import AsyncIterator

import openai

from mascarade.config import is_secret_configured, settings
from mascarade.router.providers.base import LLMProvider, LLMResponse, make_retry

_retry = make_retry(
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
)


class HuggingFaceProvider(LLMProvider):
    name = "huggingface"
    default_model = settings.huggingface_model
    cost_per_million = (0.0, 0.0)
    speed_rank = 2
    quality_rank = 2

    def __init__(self) -> None:
        self._client = openai.AsyncOpenAI(
            api_key=settings.huggingface_api_key,
            base_url=settings.huggingface_base_url,
            timeout=30.0,
        )

    @property
    def is_configured(self) -> bool:
        return is_secret_configured(settings.huggingface_api_key)

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
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        response = await self._client.chat.completions.create(
            model=model,
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=model,
            provider=self.name,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
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
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

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
        return [settings.huggingface_model]
