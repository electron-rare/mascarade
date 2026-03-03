"""Registre d'agents — enregistrement, découverte et persistance."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from mascarade.agents.base import Agent
from mascarade.router.router import Strategy

DEFAULT_STORAGE_PATH = Path("data/agents.json")


class AgentRegistry:
    """Registre centralisé pour gérer les agents disponibles."""

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        self._agents: dict[str, Agent] = {}
        self._builtin_names: set[str] = set()
        self._storage_path = storage_path

    def register(self, agent: Agent, *, builtin: bool = False) -> None:
        self._agents[agent.name] = agent
        if builtin:
            self._builtin_names.add(agent.name)

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
        self._builtin_names.discard(name)

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __len__(self) -> int:
        return len(self._agents)

    # --- Persistance ---

    def save(self) -> None:
        """Sauvegarder les agents dynamiques dans un fichier JSON."""
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        agents_data = []
        for agent in self._agents.values():
            if agent.name in self._builtin_names:
                continue
            data = asdict(agent)
            data["strategy"] = agent.strategy.value if isinstance(agent.strategy, Strategy) else str(agent.strategy)
            agents_data.append(data)
        self._storage_path.write_text(
            json.dumps(agents_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load(self) -> None:
        """Charger les agents dynamiques depuis le fichier JSON."""
        if self._storage_path is None or not self._storage_path.exists():
            return
        raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        for data in raw:
            data["strategy"] = Strategy(data["strategy"])
            agent = Agent(**data)
            self.register(agent)
