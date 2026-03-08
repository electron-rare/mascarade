"""Adaptateur Google Gemini (API key ou Vertex AI)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from google import genai
from google.auth.transport.requests import Request
from google.genai import types as genai_types
from google.oauth2.credentials import Credentials

from mascarade.config import is_secret_configured, settings
from mascarade.router.providers.base import LLMProvider, LLMResponse, make_retry

_retry = make_retry()

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


def _messages_to_text(messages: list[dict], system: str | None = None) -> str:
    chunks: list[str] = []
    if system:
        chunks.append(f"[system]\n{system.strip()}\n")
    for message in messages:
        role = message.get("role", "user")
        content = str(message.get("content", "")).strip()
        chunks.append(f"[{role}] {content}")
    return "\n".join(chunks).strip()


class GoogleProvider(LLMProvider):
    name = "google"
    default_model = settings.google_model
    cost_per_million = (1.25, 5.0)
    speed_rank = 1
    quality_rank = 2

    def __init__(self) -> None:
        if settings.google_application_credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials

        self._client: genai.Client | None = None
        self._client_token = ""
        self._client_mode = ""

    @property
    def is_configured(self) -> bool:
        auth_mode = _normalized_auth_mode()
        if auth_mode == "api_key":
            return is_secret_configured(settings.google_api_key)
        if auth_mode == "oauth_oidc":
            return bool(
                settings.google_oauth_client_id.strip()
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

    def _build_oauth_credentials(self) -> Credentials:
        token_endpoint = settings.google_oauth_token_endpoint.strip()
        refresh_token = settings.google_oauth_refresh_token.strip()
        client_id = settings.google_oauth_client_id.strip()
        client_secret = settings.google_oauth_client_secret.strip()
        access_token = settings.google_oauth_access_token.strip()
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
        access_token = settings.google_oauth_access_token.strip()
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

    def _ensure_client(self) -> genai.Client:
        auth_mode = _normalized_auth_mode()
        http_opts = genai_types.HttpOptions(timeout=_TIMEOUT_S)

        if auth_mode == "api_key":
            api_key = settings.google_api_key.strip()
            if not is_secret_configured(api_key):
                raise RuntimeError("Google API key is missing")
            if (
                self._client is not None
                and self._client_mode == auth_mode
                and self._client_token == api_key
            ):
                return self._client
            self._client = genai.Client(api_key=api_key, http_options=http_opts)
            self._client_token = api_key
            self._client_mode = auth_mode
            return self._client

        if auth_mode == "oauth_oidc":
            credentials = self._resolve_oauth_credentials()
            token = credentials.token or ""
            use_vertex = bool(settings.google_cloud_project.strip())
            client_mode = f"{auth_mode}:{'vertex' if use_vertex else 'gemini'}"
            if (
                self._client is not None
                and self._client_mode == client_mode
                and self._client_token == token
            ):
                return self._client
            client_kwargs: dict[str, object] = {
                "credentials": credentials,
                "http_options": http_opts,
            }
            if use_vertex:
                client_kwargs.update(
                    {
                        "vertexai": True,
                        "project": settings.google_cloud_project,
                        "location": settings.google_cloud_location,
                    }
                )
            self._client = genai.Client(**client_kwargs)
            self._client_token = token
            self._client_mode = client_mode
            return self._client

        adc_path = settings.google_application_credentials.strip()
        if adc_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = adc_path
        client_key = "|".join(
            [
                settings.google_cloud_project.strip(),
                settings.google_cloud_location.strip(),
                adc_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip(),
            ]
        )
        if (
            self._client is not None
            and self._client_mode == auth_mode
            and self._client_token == client_key
        ):
            return self._client
        self._client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
            http_options=http_opts,
        )
        self._client_token = client_key
        self._client_mode = auth_mode
        return self._client

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
        model_id = model or self.default_model
        prompt = _messages_to_text(messages, system=system)

        def _call():
            client = self._ensure_client()
            return client.models.generate_content(
                model=model_id,
                contents=prompt,
                config={"temperature": temperature, "max_output_tokens": max_tokens},
            )

        response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=_TIMEOUT_S)
        usage_meta = getattr(response, "usage_metadata", None)

        return LLMResponse(
            content=getattr(response, "text", "") or "",
            model=model_id,
            provider=self.name,
            usage={
                "input_tokens": int(getattr(usage_meta, "prompt_token_count", 0) or 0),
                "output_tokens": int(getattr(usage_meta, "candidates_token_count", 0) or 0),
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
        model_id = model or self.default_model
        prompt = _messages_to_text(messages, system=system)

        def _call():
            client = self._ensure_client()
            return client.models.generate_content_stream(
                model=model_id,
                contents=prompt,
                config={"temperature": temperature, "max_output_tokens": max_tokens},
            )

        stream = await asyncio.wait_for(asyncio.to_thread(_call), timeout=_TIMEOUT_S)
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield text

    def available_models(self) -> list[str]:
        return [settings.google_model]
