"""Registre d'agents — enregistrement et découverte."""

from __future__ import annotations

from mascarade.agents.base import Agent


class AgentRegistry:
    """Registre centralisé pour gérer les agents disponibles."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent:
        if name not in self._agents:
            raise KeyError(
                f"Agent '{name}' non trouvé. Disponibles: {list(self._agents.keys())}"
            )
        return self._agents[name]

    def list(self) -> list[Agent]:
        return list(self._agents.values())

    def remove(self, name: str) -> None:
        self._agents.pop(name, None)

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __len__(self) -> int:
        return len(self._agents)
