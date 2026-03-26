"""A2A Agent Card — /.well-known/agent.json per Google A2A spec."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AgentCard:
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: list[str] = field(default_factory=list)
    skills: list[dict[str, str]] = field(default_factory=list)
    provider: str = "mascarade"
    authentication: dict[str, Any] = field(
        default_factory=lambda: {"type": "bearer", "required": False}
    )

    def to_dict(self) -> dict:
        return asdict(self)


def generate_agent_card(agent: Any, base_url: str = "http://localhost:8100") -> AgentCard:
    name = getattr(agent, "name", getattr(agent, "id", "unknown"))
    desc = getattr(agent, "description", "")
    category = getattr(agent, "category", "core")
    model = getattr(agent, "model", "")
    skills = []
    for skill_name in getattr(agent, "skills", []):
        skills.append({"name": skill_name, "description": f"{name} skill: {skill_name}"})
    return AgentCard(
        name=name,
        description=desc,
        url=f"{base_url}/a2a",
        capabilities=["chat", "task", f"category:{category}"],
        skills=skills,
        provider=f"mascarade/{model}" if model else "mascarade",
    )
