"""Registre d'agents — enregistrement, découverte et persistance."""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from mascarade.agents.base import Agent
from mascarade.agents.prompt_versioning import iso_utc_now
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
        self._lock = asyncio.Lock()

    def register(self, agent: Agent, *, builtin: bool = False) -> None:
        self._agents[agent.name] = agent
        if builtin:
            self._builtin_names.add(agent.name)

    async def async_register(self, agent: Agent, *, builtin: bool = False) -> None:
        """Thread-safe register for use from async contexts."""
        async with self._lock:
            self.register(agent, builtin=builtin)

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

    async def async_remove(self, name: str) -> None:
        """Thread-safe remove for use from async contexts."""
        async with self._lock:
            self.remove(name)

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

    # --- Capabilities & Delegation ---

    def find_by_capability(self, capability: str) -> list[Agent]:
        """Find agents that declare a specific capability."""
        return [
            a for a in self._agents.values()
            if capability in (a.capabilities or [])
        ]

    def find_by_cluster(self, cluster: str) -> list[Agent]:
        """Find all agents in a domain cluster."""
        return [
            a for a in self._agents.values()
            if a.cluster == cluster
        ]

    def find_best_for(self, task_description: str) -> Agent | None:
        """Find the best agent for a task based on capabilities and keywords.

        Simple keyword matching against agent descriptions and capabilities.
        For LLM-based routing, use the Plan-and-Execute orchestrator instead.
        """
        task_lower = task_description.lower()
        best: Agent | None = None
        best_score = 0

        for agent in self._agents.values():
            score = 0
            # Match capabilities
            for cap in (agent.capabilities or []):
                if cap.lower() in task_lower:
                    score += 3
            # Match description keywords
            desc_words = (agent.description or "").lower().split()
            for word in desc_words:
                if len(word) > 3 and word in task_lower:
                    score += 1
            # Match name
            if agent.name.replace("-", " ").replace("_", " ") in task_lower:
                score += 5

            if score > best_score:
                best_score = score
                best = agent

        return best

    def clusters(self) -> dict[str, list[Agent]]:
        """Return all agents grouped by cluster."""
        groups: dict[str, list[Agent]] = {}
        for agent in self._agents.values():
            cluster = agent.cluster or "uncategorized"
            groups.setdefault(cluster, []).append(agent)
        return groups

    # --- Persistance ---

    async def async_save(self) -> None:
        """Thread-safe save for use from async contexts."""
        async with self._lock:
            self.save()

    async def async_load(self) -> None:
        """Thread-safe load for use from async contexts."""
        async with self._lock:
            self.load()

    def save(self) -> None:
        """Sauvegarder les agents dynamiques dans un fichier JSON."""
        if self._storage_path is None:
            return

        # Load previous state to detect prompt changes
        previous_agents = {}
        if self._storage_path.exists():
            try:
                raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
                for data in raw:
                    previous_agents[data["name"]] = {
                        "system_prompt": data.get("system_prompt", ""),
                        "prompt_versions": data.get("prompt_versions", []),
                    }
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load previous agents for versioning: %s", exc)

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        agents_data = []
        for agent in self._agents.values():
            if agent.name in self._builtin_names:
                continue

            # Check for prompt changes and create version if needed
            previous = previous_agents.get(agent.name)
            if previous is not None:
                previous_prompt = previous["system_prompt"]
                if previous_prompt != agent.system_prompt:
                    # Restore previous versions from disk
                    agent.prompt_versions = previous["prompt_versions"]

                    # Create a version entry for the OLD prompt (before the change)
                    version_number = len(agent.prompt_versions) + 1

                    # Compute diff from previous prompt to current prompt
                    diff = self._compute_diff(previous_prompt, agent.system_prompt)

                    version_entry = {
                        "version_number": version_number,
                        "timestamp": iso_utc_now(),
                        "content": previous_prompt,
                        "author_hash": "system",
                        "diff": diff,
                        "note": None,
                    }

                    agent.prompt_versions.append(version_entry)

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

    def _compute_diff(self, old_content: str, new_content: str) -> str:
        """Calculer un diff unifié entre deux contenus."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = difflib.unified_diff(
            old_lines,
            new_lines,
            lineterm="",
        )
        return "".join(diff_lines)
