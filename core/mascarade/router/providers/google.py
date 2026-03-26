"""Adaptateur Google Gemini (API key ou Vertex AI) — litellm chat path."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

try:
    import litellm
except ImportError:
    litellm = None  # type: ignore[assignment]

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from mascarade.config import is_secret_configured, secret_value, settings
from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    build_chat_messages,
    make_retry,
)

_retry = make_retry()
logger = logging.getLogger("mascarade.router.providers.google")

_TIMEOUT_S = 60
_OAUTH_REFRESH_SKEW = timedelta(seconds=60)


def _normalized_auth_mode() -> str:
    mode = settings.google_auth_mode.strip().lower()
    return mode if mode in {"api_key", "oauth_oidc", "adc"} else "api_key"


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


def _setup_auth_env() -> None:
    """Push Google auth credentials into env vars so litellm can pick them up."""
    auth_mode = _normalized_auth_mode()

    if auth_mode == "api_key":
        api_key = secret_value(settings.google_api_key).strip()
        if is_secret_configured(api_key):
            os.environ["GEMINI_API_KEY"] = api_key

    elif auth_mode == "adc":
        adc_path = settings.google_application_credentials.strip()
        if adc_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = adc_path
        project = settings.google_cloud_project.strip()
        if project:
            os.environ["VERTEXAI_PROJECT"] = project
        location = settings.google_cloud_location.strip()
        if location:
            os.environ["VERTEXAI_LOCATION"] = location


class GoogleProvider(LLMProvider):
    name = "google"
    default_model = settings.google_model
    cost_per_million = (1.25, 5.0)
    speed_rank = 1
    quality_rank = 2

    def __init__(self) -> None:
        if settings.google_application_credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
        # Push auth env vars for litellm on init
        _setup_auth_env()

    @property
    def is_configured(self) -> bool:
        if litellm is None:
            return False
        auth_mode = _normalized_auth_mode()
        if auth_mode == "api_key":
            return is_secret_configured(settings.google_api_key)
        if auth_mode == "oauth_oidc":
            return bool(
                secret_value(settings.google_oauth_client_id).strip()
                and is_secret_configured(settings.google_oauth_client_secret)
                and (
                    is_secret_configured(settings.google_oauth_access_token)
                    or is_secret_configured(settings.google_oauth_refresh_token)
                )
            )
        return bool(
            settings.google_cloud_project.strip()
            and (
                settings.google_application_credentials.strip()
                or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
            )
        )

    # ---- OAuth helpers (kept for 3-mode auth) ----

    def _build_oauth_credentials(self) -> Credentials:
        token_endpoint = settings.google_oauth_token_endpoint.strip()
        refresh_token = secret_value(settings.google_oauth_refresh_token).strip()
        client_id = secret_value(settings.google_oauth_client_id).strip()
        client_secret = secret_value(settings.google_oauth_client_secret).strip()
        access_token = secret_value(settings.google_oauth_access_token).strip()
        expires_at = _parse_expires_at(settings.google_oauth_expires_at)

        if not token_endpoint:
            raise RuntimeError("Google OAuth token endpoint is missing")
        if not client_id:
            raise RuntimeError("Google OAuth client id is missing")
        if not is_secret_configured(client_secret):
            raise RuntimeError("Google OAuth client secret is missing")
        if not is_secret_configured(access_token) and not is_secret_configured(refresh_token):
            raise RuntimeError("Google OAuth access token or refresh token is missing")

        scopes = [
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/generative-language.retriever",
        ]
        credentials = Credentials(
            token=access_token or None,
            refresh_token=refresh_token or None,
            token_uri=token_endpoint,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )
        if expires_at is not None:
            credentials.expiry = expires_at
        return credentials

    def _resolve_oauth_credentials(self) -> Credentials:
        credentials = self._build_oauth_credentials()
        expires_at = _parse_expires_at(settings.google_oauth_expires_at)
        access_token = secret_value(settings.google_oauth_access_token).strip()
        if (
            is_secret_configured(access_token)
            and expires_at is not None
            and expires_at > datetime.now(tz=UTC) + _OAUTH_REFRESH_SKEW
        ):
            return credentials
        if is_secret_configured(access_token) and not credentials.expired:
            return credentials
        if not credentials.refresh_token:
            if is_secret_configured(access_token):
                return credentials
            raise RuntimeError("Google OAuth refresh token is missing")

        credentials.refresh(Request())
        settings.google_oauth_access_token = credentials.token or ""
        if credentials.refresh_token:
            settings.google_oauth_refresh_token = credentials.refresh_token
        settings.google_oauth_expires_at = (
            _iso_utc(credentials.expiry) if credentials.expiry else ""
        )
        return credentials

    def _ensure_oauth_env(self) -> None:
        """Refresh OAuth token and push into env for litellm."""
        credentials = self._resolve_oauth_credentials()
        token = credentials.token or ""
        if token:
            os.environ["GEMINI_API_KEY"] = token

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
        model_id = model or self.default_model

        # Ensure auth env is up-to-date (especially for OAuth refresh)
        auth_mode = _normalized_auth_mode()
        if auth_mode == "oauth_oidc":
            self._ensure_oauth_env()
        else:
            _setup_auth_env()

        chat_messages = build_chat_messages(messages, system)

        response = await litellm.acompletion(
            model=f"gemini/{model_id}",
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=_TIMEOUT_S,
        )
        if not response.choices:
            raise RuntimeError(f"Google/Gemini returned empty choices for model {model_id}")
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=model_id,
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
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        if litellm is None:
            raise RuntimeError("litellm is not installed. Install with: pip install litellm")
        model_id = model or self.default_model

        auth_mode = _normalized_auth_mode()
        if auth_mode == "oauth_oidc":
            self._ensure_oauth_env()
        else:
            _setup_auth_env()

        chat_messages = build_chat_messages(messages, system)

        response = await litellm.acompletion(
            model=f"gemini/{model_id}",
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=_TIMEOUT_S,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def available_models(self) -> list[str]:
        return [settings.google_model]
