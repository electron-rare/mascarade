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
    preferred_role: str | None = None
    strategy: Strategy = Strategy.BEST
    routing_policy: str = "auto"
    tools: list[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096
    prompt_versions: list[dict] = field(default_factory=list)

    def build_send_payload(
        self,
        prompt: str,
        *,
        context: list[dict] | None = None,
    ) -> dict[str, object]:
        messages = list(context) if context else []
        messages.append({"role": "user", "content": prompt})
        return {
            "messages": messages,
            "strategy": self.strategy,
            "routing_policy": self.routing_policy,
            "provider": self.preferred_provider,
            "model": self.preferred_model,
            "system": self.system_prompt,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    async def run(
        self,
        prompt: str,
        *,
        router: Router,
        context: list[dict] | None = None,
    ) -> LLMResponse:
        """Exécuter l'agent avec un prompt donné."""
        payload = self.build_send_payload(prompt, context=context)
        return await router.send(
            payload["messages"],
            strategy=payload["strategy"],
            routing_policy=payload.get("routing_policy"),
            provider=payload["provider"],
            model=payload["model"],
            system=payload["system"],
            temperature=payload["temperature"],
            max_tokens=payload["max_tokens"],
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
            routing_policy=self.routing_policy,
            provider=self.preferred_provider,
            model=self.preferred_model,
            system=self.system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
