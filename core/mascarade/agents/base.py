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
    from mascarade.agents.skill_registry import SkillRegistry


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
    skills: list[str] = field(default_factory=list)  # assigned skill names
    retry_config: dict | None = None
    prompt_versions: list[dict] = field(default_factory=list)

    def get_enhanced_system_prompt(self, skill_registry: SkillRegistry) -> str:
        """Build system prompt enhanced with assigned skills.

        Concatenates the agent's base system_prompt with instruction fragments
        from all assigned and enabled skills.
        """
        parts = [self.system_prompt]
        for skill_name in self.skills:
            try:
                skill = skill_registry.get(skill_name)
            except KeyError:
                continue
            if skill.enabled and skill.instruction:
                parts.append(skill.instruction)
        return "\n\n".join(parts)

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
        registry: AgentRegistry | None = None,
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
        registry: AgentRegistry | None = None,
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
