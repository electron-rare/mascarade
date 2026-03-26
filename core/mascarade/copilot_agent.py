"""Expose Mascarade agents as a GitHub Copilot Extension via MCP.

GitHub Copilot uses Model Context Protocol (MCP) since Nov 2025 to
integrate external tools. Mascarade already implements an MCP server
(mascarade.mcp.server) — this module provides Copilot-specific
configuration and agent skill export.

Usage:
    # In VS Code settings.json (or .github/copilot-chat.json):
    {
      "github.copilot.chat.codeGeneration.instructions": [
        {"text": "Use Mascarade MCP tools when available"}
      ],
      "mcp": {
        "servers": {
          "mascarade": {
            "type": "http",
            "url": "http://localhost:8100/mcp",
            "headers": {
              "Authorization": "Bearer ${MASCARADE_API_KEY}"
            }
          }
        }
      }
    }

    # Or via stdio for local development:
    python -m mascarade.mcp.server
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("mascarade.copilot_agent")


def export_agent_skills(
    output_dir: str | Path = ".github/skills",
    agents: list[dict] | None = None,
) -> list[Path]:
    """Export Mascarade agents as Copilot Agent Skills.

    Creates SKILL.md files compatible with the agentskills open standard.
    Each agent becomes a skill that Copilot can activate contextually.

    Args:
        output_dir: Directory to write skill files to.
        agents: List of agent dicts (name, description, system_prompt).
                If None, uses a sensible default set.

    Returns:
        List of created file paths.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if agents is None:
        agents = _default_agents()

    created: list[Path] = []
    for agent in agents:
        skill_dir = output_path / agent["name"]
        skill_dir.mkdir(exist_ok=True)

        skill_md = skill_dir / "SKILL.md"
        content = _render_skill_md(agent)
        skill_md.write_text(content, encoding="utf-8")
        created.append(skill_md)

        logger.info("Exported skill: %s → %s", agent["name"], skill_md)

    # Write index
    index = output_path / "README.md"
    index.write_text(
        f"# Mascarade Agent Skills\n\n"
        f"Auto-generated from Mascarade agent registry.\n"
        f"{len(created)} skills exported.\n",
        encoding="utf-8",
    )

    return created


def generate_copilot_mcp_config(
    base_url: str = "http://localhost:8100",
    api_key: str = "${MASCARADE_API_KEY}",
) -> dict:
    """Generate MCP server configuration for GitHub Copilot.

    Returns a dict suitable for VS Code settings.json or
    .github/copilot-chat.json.
    """
    return {
        "mcp": {
            "servers": {
                "mascarade": {
                    "type": "http",
                    "url": f"{base_url}/mcp",
                    "headers": {
                        "Authorization": f"Bearer {api_key}",
                    },
                },
            },
        },
    }


def generate_copilot_instructions(agents: list[dict] | None = None) -> str:
    """Generate .github/copilot-instructions.md for the project.

    Tells Copilot how to use Mascarade tools effectively.
    """
    if agents is None:
        agents = _default_agents()

    agent_list = "\n".join(f"- **{a['name']}**: {a['description']}" for a in agents)

    return f"""\
# Copilot Instructions — Mascarade Integration

This project uses Mascarade as its LLM orchestration backend.
Mascarade agents are available as MCP tools.

## Available Agents

{agent_list}

## Usage

- Use `run_agent` MCP tool to delegate tasks to specialized agents
- Use `list_agents` to discover available agents and their capabilities
- Prefer domain-specific agents (kicad-designer, spice-expert) for hardware tasks
- Use agent-zero for coordination and task decomposition

## Routing

Mascarade routes to the best provider automatically.
You can specify a strategy: best, cheapest, fastest, domain, specific.
"""


def _default_agents() -> list[dict]:
    """Default agent set for skill export."""
    return [
        {
            "name": "coder",
            "description": "Code review, debugging, explanation, and generation",
            "category": "code",
        },
        {
            "name": "analyst",
            "description": "Data and situation analysis with structured insights",
            "category": "analysis",
        },
        {
            "name": "kicad-designer",
            "description": "PCB design, schematics, DRC, and manufacturing with KiCad",
            "category": "electronics",
        },
        {
            "name": "spice-expert",
            "description": "SPICE simulation, netlists, AC/DC/transient analysis",
            "category": "electronics",
        },
        {
            "name": "industrial-coder",
            "description": "Verilog, SystemVerilog, CUDA, embedded C, CAD scripting",
            "category": "domain",
        },
        {
            "name": "planner",
            "description": "Task planning and project decomposition",
            "category": "orchestration",
        },
    ]


def _render_skill_md(agent: dict) -> str:
    """Render a SKILL.md file for an agent."""
    return f"""\
---
name: mascarade-{agent["name"]}
description: "{agent["description"]}"
license: MIT
---

# {agent["name"]}

{agent["description"]}

## Instructions

Use the Mascarade MCP `run_agent` tool to invoke this agent:

```
run_agent(agent="{agent["name"]}", message="<your request>")
```

This agent is specialized for {agent.get("category", "general")} tasks
and will be routed to the best available LLM provider automatically.
"""
