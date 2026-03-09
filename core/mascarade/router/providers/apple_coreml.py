"""Adapter for the host-native Apple LLM service."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

from mascarade.config import settings
from mascarade.router.providers.base import LLMProvider, LLMResponse, make_retry

logger = logging.getLogger("mascarade.providers.apple_coreml")

_retry = make_retry(httpx.ConnectError)


class AppleCoreMLProvider(LLMProvider):
    name = "apple-coreml"
    default_model = "apple-local"
    cost_per_million = (0.0, 0.0)
    speed_rank = 1
    quality_rank = 2

    def __init__(self) -> None:
        self._base_url = settings.apple_llm_base_url.rstrip("/")
        self.default_model = settings.apple_llm_model_id or self.default_model
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=settings.apple_llm_timeout_seconds,
        )

    @property
    def is_configured(self) -> bool:
        if not self._base_url:
            return False
        if settings.apple_llm_enabled:
            return True
        return self._base_url != "http://apple-llm:8201"

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

        payload = {
            "messages": messages,
            "system": system,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            response = await self._client.post("/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                "Apple local timeout after "
                f"{settings.apple_llm_timeout_seconds:.0f}s for model '{model}' "
                f"(max_tokens={max_tokens}). "
                "Increase APPLE_LLM_TIMEOUT_SECONDS or lower max_tokens. "
                "A cold-start Core ML warm-up can take several minutes."
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            raise RuntimeError(
                f"Apple local HTTP {exc.response.status_code} for model '{model}': {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Apple local request failed for model '{model}': {exc}"
            ) from exc

        return LLMResponse(
            content=data.get("content", ""),
            model=data.get("model", model),
            provider=self.name,
            usage=data.get("usage", {}),
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
        response = await self.send(
            messages,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if response.content:
            yield response.content

    def available_models(self) -> list[str]:
        try:
            with httpx.Client(base_url=self._base_url, timeout=5.0) as client:
                resp = client.get("/models")
                resp.raise_for_status()
                models = resp.json().get("models", [])
                if isinstance(models, list) and models:
                    return [str(model) for model in models]
        except Exception:
            logger.warning("Cannot list Apple LLM models at %s", self._base_url)
        return [self.default_model]
