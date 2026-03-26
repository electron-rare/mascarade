"""Adaptateur Hugging Face Inference — litellm chat path."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

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

_retry = make_retry(ConnectionError, TimeoutError)
_OAUTH_REFRESH_SKEW = timedelta(seconds=60)
logger = logging.getLogger("mascarade.router.providers.huggingface")


def _normalized_auth_mode() -> str:
    mode = settings.huggingface_auth_mode.strip().lower()
    return mode if mode in {"api_key", "oauth_oidc"} else "api_key"


def _parse_expires_at(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        return datetime.fromisoformat(normalized).astimezone(UTC)
    except ValueError:
        return None


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class HuggingFaceProvider(LLMProvider):
    name = "huggingface"
    default_model = settings.huggingface_model
    cost_per_million = (0.0, 0.0)
    speed_rank = 2
    quality_rank = 2

    def __init__(self) -> None:
        self._client_token = ""
        self._client_mode = ""

    @property
    def is_configured(self) -> bool:
        if litellm is None:
            return False
        if _normalized_auth_mode() == "api_key":
            return is_secret_configured(settings.huggingface_api_key)
        return bool(
            is_secret_configured(settings.huggingface_oauth_access_token)
            or (
                is_secret_configured(settings.huggingface_oauth_refresh_token)
                and secret_value(settings.huggingface_oauth_client_id).strip()
                and is_secret_configured(settings.huggingface_oauth_client_secret)
            )
        )

    # ---- OAuth token refresh (kept intact) ----

    async def _refresh_oauth_access_token(self) -> str:
        token_endpoint = settings.huggingface_oauth_token_endpoint.strip()
        refresh_token = secret_value(settings.huggingface_oauth_refresh_token).strip()
        client_id = secret_value(settings.huggingface_oauth_client_id).strip()
        client_secret = secret_value(settings.huggingface_oauth_client_secret).strip()

        if not token_endpoint:
            raise RuntimeError("Hugging Face OAuth token endpoint is missing")
        if not is_secret_configured(refresh_token):
            raise RuntimeError("Hugging Face OAuth refresh token is missing")
        if not client_id:
            raise RuntimeError("Hugging Face OAuth client id is missing")
        if not is_secret_configured(client_secret):
            raise RuntimeError("Hugging Face OAuth client secret is missing")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Accept": "application/json"},
            )
        response.raise_for_status()
        payload = response.json()
        access_token = str(payload.get("access_token") or "").strip()
        if not is_secret_configured(access_token):
            raise RuntimeError("Hugging Face OAuth refresh returned no access token")

        settings.huggingface_oauth_access_token = access_token
        refreshed_refresh_token = str(payload.get("refresh_token") or "").strip()
        if is_secret_configured(refreshed_refresh_token):
            settings.huggingface_oauth_refresh_token = refreshed_refresh_token

        expires_in = payload.get("expires_in")
        if isinstance(expires_in, int | float) and expires_in > 0:
            settings.huggingface_oauth_expires_at = _iso_utc(
                datetime.now(tz=UTC) + timedelta(seconds=int(expires_in))
            )

        return access_token

    async def _resolve_oauth_access_token(self) -> str:
        access_token = secret_value(settings.huggingface_oauth_access_token).strip()
        expires_at = _parse_expires_at(settings.huggingface_oauth_expires_at)
        if is_secret_configured(access_token):
            if expires_at is None or expires_at > datetime.now(tz=UTC) + _OAUTH_REFRESH_SKEW:
                return access_token
        return await self._refresh_oauth_access_token()

    async def _resolve_access_token(self) -> str:
        if _normalized_auth_mode() == "api_key":
            token = secret_value(settings.huggingface_api_key).strip()
            if not is_secret_configured(token):
                raise RuntimeError("Hugging Face API key is missing")
            return token
        return await self._resolve_oauth_access_token()

    # ---- litellm chat paths ----

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
        if litellm is None:
            raise RuntimeError("litellm is not installed. Install with: pip install litellm")
        model = model or self.default_model
        chat_messages = build_chat_messages(messages, system)

        api_key = await self._resolve_access_token()

        response = await litellm.acompletion(
            model=f"huggingface/{model}",
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            api_key=api_key,
        )
        if not response.choices:
            raise RuntimeError(f"HuggingFace returned empty choices for model {model}")
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

        api_key = await self._resolve_access_token()

        response = await litellm.acompletion(
            model=f"huggingface/{model}",
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            api_key=api_key,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def available_models(self) -> list[str]:
        return [settings.huggingface_model]
