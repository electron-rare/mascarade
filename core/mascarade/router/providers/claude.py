"""Adaptateur Anthropic Claude."""

from __future__ import annotations

from collections.abc import AsyncIterator

import anthropic
import openai

from mascarade.config import is_secret_configured, settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

_retry = make_retry(
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
)


class ClaudeProvider(LLMProvider):
    name = "claude"
    default_model = "claude-sonnet-4-6"
    cost_per_million = (3.0, 15.0)
    speed_rank = 2
    quality_rank = 3

    def __init__(self) -> None:
        self._proxy_enabled = bool(
            settings.litellm_proxy_enabled
            and settings.litellm_base_url.strip()
            and is_secret_configured(settings.litellm_master_key)
        )
        if self._proxy_enabled:
            self._client = openai.AsyncOpenAI(
                api_key=settings.litellm_master_key,
                base_url=settings.litellm_base_url,
                timeout=30.0,
            )
        else:
            self._client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=30.0,
            )

    @property
    def is_configured(self) -> bool:
        if self._proxy_enabled:
            return bool(
                settings.litellm_base_url.strip()
                and is_secret_configured(settings.litellm_master_key)
            )
        return is_secret_configured(settings.anthropic_api_key)

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
        if self._proxy_enabled:
            chat_messages = build_chat_messages(messages, system)
            response = await self._client.chat.completions.create(
                model=model,
                messages=chat_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if not response.choices:
                raise RuntimeError(f"Claude proxy returned empty choices for model {model}")
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

        kwargs: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)
        content = response.content[0].text if response.content else ""
        usage = response.usage
        return LLMResponse(
            content=content,
            model=model,
            provider=self.name,
            usage={
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
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
        if self._proxy_enabled:
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
            return

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
