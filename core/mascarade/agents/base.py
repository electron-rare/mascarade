"""Agent de base — brique fondamentale de l'orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mascarade.router import Router
from mascarade.router.providers.base import LLMResponse
from mascarade.router.router import Strategy

if TYPE_CHECKING:
    from mascarade.agents.registry import AgentRegistry


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
    tools: list[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096

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
        registry: AgentRegistry | None = None,
    ) -> LLMResponse:
        """Exécuter l'agent avec un prompt donné."""
        start_time = time.perf_counter()
        success = False
        response = None

        try:
            payload = self.build_send_payload(prompt, context=context)
            response = await router.send(
                payload["messages"],
                strategy=payload["strategy"],
                provider=payload["provider"],
                model=payload["model"],
                system=payload["system"],
                temperature=payload["temperature"],
                max_tokens=payload["max_tokens"],
            )
            success = True
            return response
        finally:
            elapsed = time.perf_counter() - start_time
            if registry:
                tokens = 0
                if success and response and response.usage:
                    tokens = sum(response.usage.values())
                cost = 0.0  # Cost is tracked by router, we track tokens here
                registry.track_agent_usage(
                    agent_name=self.name,
                    tokens=tokens,
                    cost=cost,
                    response_time=elapsed,
                    success=success,
                )

    async def run_with_history(
        self,
        messages: list[dict],
        *,
        router: Router,
        registry: AgentRegistry | None = None,
    ) -> LLMResponse:
        """Exécuter l'agent avec un historique de messages complet."""
        start_time = time.perf_counter()
        success = False
        response = None

        try:
            response = await router.send(
                messages,
                strategy=self.strategy,
                provider=self.preferred_provider,
                model=self.preferred_model,
                system=self.system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            success = True
            return response
        finally:
            elapsed = time.perf_counter() - start_time
            if registry:
                tokens = 0
                if success and response and response.usage:
                    tokens = sum(response.usage.values())
                cost = 0.0  # Cost is tracked by router, we track tokens here
                registry.track_agent_usage(
                    agent_name=self.name,
                    tokens=tokens,
                    cost=cost,
                    response_time=elapsed,
                    success=success,
                )
