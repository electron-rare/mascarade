"""Contexte d'orchestration multi-agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OrchestrationContext:
    """Contexte transmis lors d'une orchestration."""

    prompt: str
    agent_names: list[str] = field(default_factory=list)
    mode: str | None = None
    current_input: str | None = None
    initial_prompt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Sérialise le contexte en dictionnaire."""
        return {
            "prompt": self.prompt,
            "agent_names": self.agent_names,
            "mode": self.mode,
            "current_input": self.current_input,
            "initial_prompt": self.initial_prompt,
        }
