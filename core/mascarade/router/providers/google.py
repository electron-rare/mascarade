"""Adaptateur Google Gemini (API key ou Vertex AI)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

from google import genai

from mascarade.config import is_secret_configured, settings
from mascarade.router.providers.base import LLMProvider, LLMResponse, make_retry

_retry = make_retry()


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
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
                settings.google_application_credentials
            )

        self._client: genai.Client | None = None

    @property
    def is_configured(self) -> bool:
        has_api_key = is_secret_configured(settings.google_api_key)
        has_vertex = bool(
            settings.google_cloud_project.strip()
            and (
                settings.google_application_credentials.strip()
                or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
            )
        )
        return has_api_key or has_vertex

    def _ensure_client(self) -> genai.Client:
        if self._client is not None:
            return self._client

        api_key = (
            settings.google_api_key
            if is_secret_configured(settings.google_api_key)
            else None
        )
        if api_key:
            self._client = genai.Client(api_key=api_key)
        else:
            self._client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
            )
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

        response = await asyncio.to_thread(_call)
        usage_meta = getattr(response, "usage_metadata", None)

        return LLMResponse(
            content=getattr(response, "text", "") or "",
            model=model_id,
            provider=self.name,
            usage={
                "input_tokens": int(getattr(usage_meta, "prompt_token_count", 0) or 0),
                "output_tokens": int(
                    getattr(usage_meta, "candidates_token_count", 0) or 0
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
        model_id = model or self.default_model
        prompt = _messages_to_text(messages, system=system)

        def _call():
            client = self._ensure_client()
            return client.models.generate_content_stream(
                model=model_id,
                contents=prompt,
                config={"temperature": temperature, "max_output_tokens": max_tokens},
            )

        stream = await asyncio.to_thread(_call)
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield text

    def available_models(self) -> list[str]:
        return [settings.google_model]
