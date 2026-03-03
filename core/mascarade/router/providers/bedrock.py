"""Adaptateur AWS Bedrock."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from mascarade.config import is_secret_configured, settings
from mascarade.router.providers.base import LLMProvider, LLMResponse, make_retry

_retry = make_retry(BotoCoreError, ClientError)


def _to_bedrock_messages(messages: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for message in messages:
        role = message.get("role", "user")
        if role not in {"user", "assistant"}:
            role = "user"
        normalized.append(
            {
                "role": role,
                "content": [{"text": message.get("content", "")}],
            }
        )
    return normalized


class BedrockProvider(LLMProvider):
    name = "bedrock"
    default_model = settings.aws_bedrock_model_id
    cost_per_million = (3.0, 15.0)
    speed_rank = 2
    quality_rank = 3

    def __init__(self) -> None:
        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            aws_session_token=settings.aws_session_token or None,
            region_name=settings.aws_region,
        )
        self._client = session.client("bedrock-runtime")

    @property
    def is_configured(self) -> bool:
        return bool(
            is_secret_configured(settings.aws_access_key_id)
            and is_secret_configured(settings.aws_secret_access_key)
        )

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

        def _call() -> dict:
            kwargs: dict = {
                "modelId": model_id,
                "messages": _to_bedrock_messages(messages),
                "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
            }
            if system:
                kwargs["system"] = [{"text": system}]
            return self._client.converse(**kwargs)

        response = await asyncio.to_thread(_call)
        parts = response.get("output", {}).get("message", {}).get("content", [])
        usage = response.get("usage", {}) or {}
        content = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        return LLMResponse(
            content=content,
            model=model_id,
            provider=self.name,
            usage={
                "input_tokens": int(usage.get("inputTokens", 0)),
                "output_tokens": int(usage.get("outputTokens", 0)),
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

        def _call() -> dict:
            kwargs: dict = {
                "modelId": model_id,
                "messages": _to_bedrock_messages(messages),
                "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
            }
            if system:
                kwargs["system"] = [{"text": system}]
            return self._client.converse_stream(**kwargs)

        response = await asyncio.to_thread(_call)
        for event in response.get("stream", []):
            text = event.get("contentBlockDelta", {}).get("delta", {}).get("text")
            if text:
                yield text

    def available_models(self) -> list[str]:
        return [settings.aws_bedrock_model_id]
