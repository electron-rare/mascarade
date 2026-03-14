"""Adaptateur Mistral AI."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import openai
from mistralai import Mistral

from mascarade.config import is_secret_configured, settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

_retry = make_retry(httpx.TimeoutException, httpx.TransportError)


class MistralProvider(LLMProvider):
    name = "mistral"
    default_model = "mistral-large-latest"
    cost_per_million = (2.0, 6.0)
    speed_rank = 1
    quality_rank = 1

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
                timeout=max(settings.mistral_timeout_ms / 1000, 1),
            )
        else:
            self._client = Mistral(
                api_key=settings.mistral_api_key,
                timeout_ms=settings.mistral_timeout_ms,
            )

    @property
    def is_configured(self) -> bool:
        if self._proxy_enabled:
            return bool(
                settings.litellm_base_url.strip()
                and is_secret_configured(settings.litellm_master_key)
            )
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
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        if self._proxy_enabled:
            response = await self._client.chat.completions.create(
                model=model,
                messages=chat_messages,
                response_format=response_format,
                max_tokens=max_tokens,
                temperature=temperature,
            )
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

        response = await self._client.chat.complete_async(
            model=model,
            messages=chat_messages,
            response_format=response_format,
            max_tokens=max_tokens,
            temperature=temperature,
        )
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
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        if self._proxy_enabled:
            response = await self._client.chat.completions.create(
                model=model,
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
            return

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
