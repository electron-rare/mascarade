"""Agent de base — brique fondamentale de l'orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from mascarade.router import Router
from mascarade.router.providers.base import LLMResponse
from mascarade.router.router import Strategy


@dataclass
class Agent:
    """Un agent spécialisé avec son propre contexte et comportement."""

    name: str
    description: str
    system_prompt: str
    preferred_provider: str | None = None
    preferred_model: str | None = None
    strategy: Strategy = Strategy.BEST
    tools: list[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096

    async def run(
        self,
        prompt: str,
        *,
        router: Router,
        context: list[dict] | None = None,
    ) -> LLMResponse:
        """Exécuter l'agent avec un prompt donné."""
        messages = list(context) if context else []
        messages.append({"role": "user", "content": prompt})

        return await router.send(
            messages,
            strategy=self.strategy,
            provider=self.preferred_provider,
            model=self.preferred_model,
            system=self.system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    async def run_with_history(
        self,
        messages: list[dict],
        *,
        router: Router,
    ) -> LLMResponse:
        """Exécuter l'agent avec un historique de messages complet."""
        return await router.send(
            messages,
            strategy=self.strategy,
            provider=self.preferred_provider,
            model=self.preferred_model,
            system=self.system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
