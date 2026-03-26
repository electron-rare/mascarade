"""Codestral provider — Mistral's code-specialized model with FIM support.

Chat completions via litellm; FIM endpoint kept as direct httpx (litellm has no FIM).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

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

logger = logging.getLogger("mascarade.providers.codestral")

_retry = make_retry(ConnectionError, TimeoutError)

# Codestral FIM endpoint (kept as direct httpx — litellm has no FIM support)
_CODESTRAL_FIM_URL = "https://codestral.mistral.ai/v1/fim/completions"


class CodestralProvider(LLMProvider):
    """Mistral Codestral — code-specialized LLM with Fill-in-the-Middle."""

    name = "codestral"
    default_model = "codestral-latest"
    cost_per_million = (0.3, 0.9)  # USD per 1M tokens
    speed_rank = 1
    quality_rank = 3  # High quality for code tasks

    def __init__(self) -> None:
        api_key = secret_value(getattr(settings, "codestral_api_key", "") or "")
        self._api_key = api_key.strip()
        timeout = getattr(settings, "codestral_timeout_seconds", 120.0)
        # httpx client kept for FIM endpoint only
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )

    @property
    def is_configured(self) -> bool:
        if litellm is None:
            return False
        return is_secret_configured(self._api_key)

    def available_models(self) -> list[str]:
        return ["codestral-latest", "codestral-2501"]

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
        """Send a chat completion request via litellm."""
        if litellm is None:
            raise RuntimeError("litellm is not installed. Install with: pip install litellm")
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        kwargs: dict = {
            "model": f"codestral/{model}",
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "api_key": self._api_key,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await litellm.acompletion(**kwargs)
        if not response.choices:
            raise RuntimeError(f"Codestral returned empty choices for model {model}")

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=model,
            provider=self.name,
            usage={
                "input_tokens": (response.usage.prompt_tokens if response.usage else 0),
                "output_tokens": (response.usage.completion_tokens if response.usage else 0),
            },
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
        """Stream chat completion tokens via litellm."""
        if litellm is None:
            raise RuntimeError("litellm is not installed. Install with: pip install litellm")
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        kwargs: dict = {
            "model": f"codestral/{model}",
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "api_key": self._api_key,
            "stream": True,
        }

        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def fill_in_middle(
        self,
        prompt: str,
        suffix: str = "",
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        stop: list[str] | None = None,
    ) -> str:
        """Codestral FIM (Fill-in-the-Middle) completion for code infilling.

        Uses direct httpx — litellm does not support FIM.

        Args:
            prompt: Code before the cursor position.
            suffix: Code after the cursor position.
            model: Model override.
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens: Maximum tokens to generate.
            stop: Stop sequences.

        Returns:
            The generated code to fill between prompt and suffix.
        """
        model = model or self.default_model
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "suffix": suffix,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stop:
            payload["stop"] = stop

        resp = await self._client.post(_CODESTRAL_FIM_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("text", "") or choices[0].get("message", {}).get("content", "")
