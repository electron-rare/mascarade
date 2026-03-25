"""GitHub Copilot provider — routes through copilot-api sidecar (OpenAI-compatible)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import openai

from mascarade.config import is_secret_configured, secret_value, settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

logger = logging.getLogger("mascarade.providers.github_copilot")

_retry = make_retry(
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
)

# Models included in Copilot plans (0x premium multiplier = effectively free)
_FREE_TIER_MODELS = [
    "gpt-5-mini",
    "gpt-4.1",
    "gpt-4o",
]

# All known models available via Copilot
_ALL_MODELS = [
    "gpt-5-mini",
    "gpt-4.1",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-5",
    "gpt-3.5-turbo",
    "claude-sonnet-4",
    "claude-sonnet-4.5",
    "claude-3.7-sonnet",
    "gemini-2.0-flash-001",
    "gemini-2.5-pro",
    "o3-mini",
    "o4-mini",
]


class GitHubCopilotProvider(LLMProvider):
    """GitHub Copilot via copilot-api sidecar proxy.

    Requires copilot-api running locally:
        npx copilot-api@latest start --port 4141

    Set GITHUB_COPILOT_PROXY_URL in .env (default: http://localhost:4141).
    Authentication is handled by the proxy (GitHub device flow).
    """

    name = "github-copilot"
    default_model = "gpt-4.1"
    cost_per_million = (0.0, 0.0)  # Covered by Copilot subscription
    speed_rank = 1
    quality_rank = 3

    def __init__(self) -> None:
        base_url = settings.github_copilot_proxy_url.rstrip("/")
        # copilot-api handles auth internally, no API key needed
        api_key = (
            secret_value(settings.github_copilot_api_key)
            if is_secret_configured(settings.github_copilot_api_key)
            else "copilot-proxy"
        )
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=f"{base_url}/v1",
            timeout=60.0,
        )
        self._base_url = base_url
        self._models_cache: list[str] | None = None

    @property
    def is_configured(self) -> bool:
        return bool(settings.github_copilot_proxy_url.strip())

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

        kwargs: dict = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format and response_format.get("type") == "json_object":
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._client.chat.completions.create(**kwargs)
        if not response.choices:
            raise RuntimeError(
                f"GitHub Copilot returned empty choices for model {model}"
            )

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=model,
            provider=self.name,
            usage={
                "input_tokens": (
                    response.usage.prompt_tokens if response.usage else 0
                ),
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
        """Return models available via Copilot.

        Falls back to static list if proxy is unreachable.
        """
        if self._models_cache is not None:
            return self._models_cache

        try:
            import httpx

            with httpx.Client(
                base_url=self._base_url, timeout=5.0
            ) as client:
                resp = client.get("/v1/models")
                resp.raise_for_status()
                models = [
                    m["id"] for m in resp.json().get("data", [])
                ]
                self._models_cache = models
                return models
        except Exception:
            logger.debug(
                "Cannot fetch models from copilot-api, using static list"
            )
            return _ALL_MODELS
