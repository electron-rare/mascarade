"""Skill dataclass — a composable capability assignable to agents."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Skill:
    """A reusable capability that can be assigned to agents.

    Skills inject instruction fragments, tool access, and few-shot examples
    into an agent's context when activated.
    """

    name: str  # unique identifier (slug)
    description: str  # human-readable description
    category: str  # e.g. "text", "code", "analysis", "creative", "domain"
    instruction: str  # system prompt fragment injected into agent context
    tools: list[str] = field(default_factory=list)  # tool names this skill enables
    examples: list[dict] = field(default_factory=list)  # [{"input": "...", "output": "..."}]
    enabled: bool = True
    version: int = 1
