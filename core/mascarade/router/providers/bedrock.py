"""Adaptateur AWS Bedrock avec support des modeles fine-tunes."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from mascarade.config import is_secret_configured, settings
from mascarade.router.providers.base import LLMProvider, LLMResponse, make_retry

logger = logging.getLogger("mascarade.bedrock")

_retry = make_retry(BotoCoreError, ClientError)

# Region where fine-tuned models are hosted
FINETUNE_REGION = "us-west-2"

_TIMEOUT_S = 60
_BOTO_CFG = BotoConfig(
    connect_timeout=10,
    read_timeout=_TIMEOUT_S,
    retries={"max_attempts": 0},  # tenacity gere les retries
)

# Domain-to-custom-model mapping (populated by discover_custom_models)
DOMAIN_MODELS: dict[str, str] = {}


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
        self._client = None
        self._ft_runtime = None
        self._ft_management = None
        self._custom_models: dict[str, str] = {}
        self._custom_models_loaded = False

    def _ensure_clients(self) -> None:
        """Create AWS clients lazily to keep startup fast."""
        if (
            self._client is not None
            and self._ft_runtime is not None
            and self._ft_management is not None
        ):
            return

        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            aws_session_token=settings.aws_session_token or None,
            region_name=settings.aws_region,
        )
        self._client = session.client("bedrock-runtime", config=_BOTO_CFG)

        ft_session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            aws_session_token=settings.aws_session_token or None,
            region_name=FINETUNE_REGION,
        )
        self._ft_runtime = ft_session.client("bedrock-runtime", config=_BOTO_CFG)
        self._ft_management = ft_session.client("bedrock")

    def _discover_custom_models(self) -> None:
        """Auto-discover mascarade-* custom models on Bedrock."""
        if self._custom_models_loaded:
            return

        self._ensure_clients()
        try:
            response = self._ft_management.list_custom_models(maxResults=50)
            for m in response.get("modelSummaries", []):
                name = m.get("modelName", "")
                arn = m.get("modelArn", "")
                if name.startswith("mascarade-"):
                    self._custom_models[name] = arn
                    DOMAIN_MODELS[name] = arn
                    logger.info("Discovered custom model: %s", name)
            if self._custom_models:
                logger.info("Found %d custom model(s)", len(self._custom_models))
        except (BotoCoreError, ClientError) as exc:
            logger.debug("Could not list custom models: %s", exc)
        finally:
            self._custom_models_loaded = True

    def _runtime_for(self, model_id: str):
        """Return the right runtime client based on model."""
        self._ensure_clients()
        if model_id in self._custom_models:
            return self._ft_runtime
        if model_id.startswith("arn:aws:bedrock:us-west-2"):
            return self._ft_runtime
        return self._client

    @property
    def is_configured(self) -> bool:
        return bool(
            is_secret_configured(settings.aws_access_key_id)
            and is_secret_configured(settings.aws_secret_access_key)
        )

    def resolve_model(self, model: str | None) -> str:
        """Resolve model name — supports 'mascarade-stm32-llama' shorthand."""
        if model is None:
            return self.default_model
        # Direct ARN
        if model.startswith("arn:"):
            return model
        # Custom model by name
        self._discover_custom_models()
        if model in self._custom_models:
            return self._custom_models[model]
        return model

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
        model_id = self.resolve_model(model)
        client = self._runtime_for(model_id)

        def _call() -> dict:
            kwargs: dict = {
                "modelId": model_id,
                "messages": _to_bedrock_messages(messages),
                "inferenceConfig": {
                    "temperature": temperature,
                    "maxTokens": max_tokens,
                },
            }
            if system:
                kwargs["system"] = [{"text": system}]
            return client.converse(**kwargs)

        response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=_TIMEOUT_S)
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
        model_id = self.resolve_model(model)
        client = self._runtime_for(model_id)

        def _call() -> dict:
            kwargs: dict = {
                "modelId": model_id,
                "messages": _to_bedrock_messages(messages),
                "inferenceConfig": {
                    "temperature": temperature,
                    "maxTokens": max_tokens,
                },
            }
            if system:
                kwargs["system"] = [{"text": system}]
            return client.converse_stream(**kwargs)

        response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=_TIMEOUT_S)
        for event in response.get("stream", []):
            text = event.get("contentBlockDelta", {}).get("delta", {}).get("text")
            if text:
                yield text

    def available_models(self) -> list[str]:
        self._discover_custom_models()
        models = [settings.aws_bedrock_model_id]
        models.extend(sorted(self._custom_models.keys()))
        return models

    def custom_models(self) -> dict[str, str]:
        """Return {name: arn} of discovered custom models."""
        self._discover_custom_models()
        return dict(self._custom_models)

    async def finetune_jobs(self) -> list[dict]:
        """List fine-tuning job statuses."""
        self._ensure_clients()

        def _call():
            return self._ft_management.list_model_customization_jobs(maxResults=20)

        response = await asyncio.to_thread(_call)
        return [
            {
                "name": j["jobName"],
                "status": j["status"],
                "model": j.get("customModelName", ""),
            }
            for j in response.get("modelCustomizationJobSummaries", [])
        ]
