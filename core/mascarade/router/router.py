"""Routeur LLM — dispatch intelligent entre providers."""

from __future__ import annotations

from enum import Enum
from typing import AsyncIterator

from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.providers.claude import ClaudeProvider
from mascarade.router.providers.openai import OpenAIProvider
from mascarade.router.providers.mistral import MistralProvider


class Strategy(str, Enum):
    BEST = "best"
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    SPECIFIC = "specific"


class Router:
    """Routeur intelligent entre providers LLM."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for provider_cls in [ClaudeProvider, OpenAIProvider, MistralProvider]:
            provider = provider_cls()
            if provider.is_configured:
                self._providers[provider.name] = provider

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.name] = provider

    @property
    def available_providers(self) -> list[str]:
        return list(self._providers.keys())

    def _select_provider(
        self,
        strategy: Strategy = Strategy.BEST,
        provider_name: str | None = None,
    ) -> LLMProvider:
        if not self._providers:
            raise RuntimeError("Aucun provider LLM configuré. Vérifiez vos clés API.")

        if strategy == Strategy.SPECIFIC:
            if not provider_name or provider_name not in self._providers:
                raise ValueError(
                    f"Provider '{provider_name}' non disponible. "
                    f"Disponibles: {self.available_providers}"
                )
            return self._providers[provider_name]

        providers = list(self._providers.values())

        if strategy == Strategy.CHEAPEST:
            return min(providers, key=lambda p: sum(p.cost_per_million))

        if strategy == Strategy.FASTEST:
            return min(providers, key=lambda p: p.speed_rank)

        # BEST — highest quality
        return max(providers, key=lambda p: p.quality_rank)

    async def send(
        self,
        messages: list[dict],
        *,
        strategy: Strategy | str = Strategy.BEST,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        strategy = Strategy(strategy)
        selected = self._select_provider(strategy, provider)
        return await selected.send(
            messages,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def stream(
        self,
        messages: list[dict],
        *,
        strategy: Strategy | str = Strategy.BEST,
        provider: str | None = None,
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        strategy = Strategy(strategy)
        selected = self._select_provider(strategy, provider)
        async for token in selected.stream(
            messages,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield token
