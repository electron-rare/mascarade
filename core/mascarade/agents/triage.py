"""Triage Agent — meta-agent that routes requests to the right agent or pipeline.

Receives any user request and decides:
  (a) which single agent to invoke, or
  (b) which pipeline of agents to chain.

Uses auto_pipeline heuristics as a fast path, falls back to a cheap LLM
classification call when heuristics are uncertain.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mascarade.agents.auto_pipeline import detect_pipeline
from mascarade.router.router import Strategy

if TYPE_CHECKING:
    from mascarade.agents.registry import AgentRegistry
    from mascarade.agents.skill_registry import SkillRegistry
    from mascarade.router import Router

logger = logging.getLogger("mascarade.agents.triage")

_TRIAGE_SYSTEM_PROMPT = """\
You are the Mascarade Triage Agent.  Your job is to analyze the user's \
request and decide how to handle it.

## Available agents
{agent_catalog}

## Instructions

Given the user request, decide:
1. **mode**: "single" if one agent can handle it, "pipeline" if the task \
requires chaining multiple agents (output of one feeds the next).
2. **agents**: ordered list of agent names (1 for single, 2+ for pipeline).
3. **reason**: one-line explanation.

Use pipeline when the task requires multiple distinct skills executed in \
sequence (e.g., "analyze then summarize", "code then review", \
"brainstorm then plan").

Output ONLY valid JSON, nothing else:
{{"mode": "single"|"pipeline", "agents": ["name", ...], "reason": "..."}}
"""


@dataclass
class TriageDecision:
    """Result of triage — which agent(s) to invoke and how."""

    mode: str  # "single" or "pipeline"
    agents: list[str]
    reason: str = ""
    confidence: float = 0.0
    source: str = "heuristic"  # "heuristic" or "llm"


class TriageAgent:
    """Meta-agent that dispatches requests to the right agent or pipeline."""

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    def _build_agent_catalog(self) -> str:
        """Build a text catalog of all agents for the LLM prompt."""
        lines = []
        for agent in self._registry.list():
            lines.append(f"- **{agent.name}**: {agent.description}")
        return "\n".join(lines)

    def _validate_agents(self, names: list[str]) -> list[str]:
        """Filter to only agents that exist in the registry."""
        valid = []
        for name in names:
            try:
                self._registry.get(name)
                valid.append(name)
            except KeyError:
                logger.warning("Triage referenced unknown agent '%s', skipping", name)
        return valid

    async def triage(
        self,
        prompt: str,
        *,
        router: Router,
        skill_registry: SkillRegistry | None = None,
        project_id: str | None = None,
        federation_scope: list[str] | None = None,
        knowledge_scope: str = "project",
    ) -> TriageDecision:
        """Analyze a prompt and decide which agent(s) to use.

        Fast path: auto_pipeline heuristics (no LLM call).
        Slow path: cheap LLM classification call.
        """
        # --- Fast path: heuristic detection ---
        all_agents = self._registry.list()
        proposal = detect_pipeline(prompt, all_agents)

        if proposal.confidence >= 0.65:
            valid = self._validate_agents(proposal.agents)
            if valid:
                return TriageDecision(
                    mode="pipeline" if proposal.should_pipeline and len(valid) > 1 else "single",
                    agents=valid,
                    reason=proposal.reason,
                    confidence=proposal.confidence,
                    source="heuristic",
                )

        # --- Slow path: LLM classification ---
        catalog = self._build_agent_catalog()
        system = _TRIAGE_SYSTEM_PROMPT.format(agent_catalog=catalog)

        try:
            response = await router.send(
                [{"role": "user", "content": prompt}],
                strategy=Strategy.ROUTELLM,
                routing_policy="cheap",
                system=system,
                temperature=0.1,
                max_tokens=256,
                project_id=project_id,
                federation_scope=federation_scope,
                knowledge_scope=knowledge_scope,
            )

            decision = self._parse_llm_response(response.content)
            if decision:
                return decision

        except Exception as exc:
            logger.warning("Triage LLM call failed: %s, falling back to heuristic", exc)

        # --- Fallback: use heuristic result even if low confidence ---
        if proposal.agents:
            valid = self._validate_agents(proposal.agents)
            if valid:
                return TriageDecision(
                    mode="pipeline" if proposal.should_pipeline and len(valid) > 1 else "single",
                    agents=valid,
                    reason=f"heuristic fallback: {proposal.reason}",
                    confidence=proposal.confidence,
                    source="heuristic-fallback",
                )

        # --- Ultimate fallback: agent-zero ---
        return TriageDecision(
            mode="single",
            agents=["agent-zero"],
            reason="no agent matched, defaulting to coordinator",
            confidence=0.3,
            source="default",
        )

    def _parse_llm_response(self, content: str) -> TriageDecision | None:
        """Parse the LLM's JSON response into a TriageDecision."""
        # Extract JSON from response (may be wrapped in markdown)
        text = content.strip()
        if "```" in text:
            # Extract from code block
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Triage LLM returned invalid JSON: %s", content[:200])
            return None

        mode = data.get("mode", "single")
        agents = data.get("agents", [])
        reason = data.get("reason", "")

        if not isinstance(agents, list) or not agents:
            logger.warning("Triage LLM returned empty agents list")
            return None

        valid = self._validate_agents(agents)
        if not valid:
            return None

        return TriageDecision(
            mode=mode if mode in ("single", "pipeline") else "single",
            agents=valid,
            reason=reason,
            confidence=0.8,
            source="llm",
        )
