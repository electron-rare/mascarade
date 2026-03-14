"""Registre d'agents — enregistrement, découverte et persistance."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from mascarade.agents.base import Agent
from mascarade.metrics.tracker import MetricsTracker
from mascarade.router.router import Strategy

logger = logging.getLogger("mascarade.agents")

DEFAULT_STORAGE_PATH = Path("data/agents.json")


class AgentRegistry:
    """Registre centralisé pour gérer les agents disponibles."""

    def __init__(self, storage_path: Path | None = DEFAULT_STORAGE_PATH) -> None:
        self._agents: dict[str, Agent] = {}
        self._builtin_names: set[str] = set()
        self._storage_path = storage_path
        self.metrics = MetricsTracker()

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

    def is_builtin(self, name: str) -> bool:
        return name in self._builtin_names

    # --- Métriques ---

    def track_agent_usage(
        self,
        agent_name: str,
        tokens: int,
        cost: float,
        response_time: float,
        success: bool,
    ) -> None:
        """Suivre l'utilisation d'un agent."""
        self.metrics.track_request(
            provider_name=agent_name,
            tokens=tokens,
            cost=cost,
            response_time=response_time,
            success=success,
        )

    def agent_metrics(self, agent_name: str) -> dict:
        """Obtenir les métriques pour un agent spécifique."""
        return self.metrics.get_provider_stats(agent_name)

    def metrics_summary(self) -> dict:
        """Obtenir un résumé de toutes les métriques des agents."""
        return self.metrics.get_summary()

    def reset_metrics(self) -> None:
        """Réinitialiser toutes les métriques."""
        self.metrics.reset()

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
            data["strategy"] = (
                agent.strategy.value
                if isinstance(agent.strategy, Strategy)
                else str(agent.strategy)
            )
            agents_data.append(data)
        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(agents_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(self._storage_path))
        except BaseException:
            os.unlink(tmp_path)
            raise

    def load(self) -> None:
        """Charger les agents dynamiques depuis le fichier JSON."""
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load agents from %s: %s", self._storage_path, exc)
            return
        for data in raw:
            try:
                data["strategy"] = Strategy(data["strategy"])
                agent = Agent(**data)
                self.register(agent)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid agent entry: %s", exc)
