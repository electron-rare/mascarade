"""Auto-pipeline detection — rule-based heuristics.

Detects when a user request should be handled by multiple agents chained
in a pipeline rather than a single agent.  No LLM call — pure regex + keyword
matching for speed and determinism.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.agents.base import Agent

# ---------------------------------------------------------------------------
# Keyword → agent-name mapping
# ---------------------------------------------------------------------------

_KEYWORD_AGENT_MAP: dict[str, list[str]] = {
    # text / analysis
    "summarize|resume|résume|résumé|tldr|synthèse|synthese": ["summarizer"],
    "translate|traduis|traduit|traduction|translation": ["translator"],
    "analyse|analyze|compare|évalue|evaluate|audit": ["analyst"],
    "plan|planifie|décompose|decompose|roadmap|todo": ["planner"],
    "brainstorm|idées|ideas|créatif|creative|imagine": ["brainstorm"],
    "write|rédige|écris|redige|reformule|rewrite": ["writer"],
    # code
    "code|debug|function|refactor|implémente|implement|programme": ["coder"],
    "review|revue|lint|check|vérifie|verify": ["coder"],
    # domain
    "spice|netlist|simulation|circuit|ampli|filtre": ["spice-expert"],
    "kicad|pcb|schéma|schema|routage|gerber|empreinte|footprint": ["kicad-expert"],
    "freecad|3d|cad|modèle|model|stl|step": ["freecad-expert"],
    "composant|component|bom|datasheet|mouser|digikey": ["components-expert"],
    "verilog|fpga|rtl|hdl|testbench|synthesis": ["verilog-expert"],
    # meta
    "classify|classifie|catégorise|categorize|intent|sentiment": ["classifier"],
    "image|illustration|prompt|diffusion|comfyui": ["image-generator"],
}

# Compiled patterns
_KEYWORD_PATTERNS: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(rf"\b(?:{kw})\b", re.IGNORECASE), agents)
    for kw, agents in _KEYWORD_AGENT_MAP.items()
]

# Sequencing connectives (FR + EN)
_SEQUENCING_PATTERN = re.compile(
    r"\b(?:then|puis|ensuite|after that|and then|et ensuite|avant de|before|"
    r"d'abord|first|finally|enfin|ensuite|next|après|after)\b",
    re.IGNORECASE,
)

# Multi-step markers
_MULTI_STEP_PATTERN = re.compile(
    r"(?:\d+[\.\)]\s|^[-•]\s|étape|step\s+\d)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class PipelineProposal:
    """Result of auto-pipeline detection."""

    should_pipeline: bool
    agents: list[str]
    confidence: float  # 0.0 - 1.0
    reason: str = ""


def detect_pipeline(
    prompt: str,
    available_agents: list[Agent] | None = None,
) -> PipelineProposal:
    """Detect whether a prompt needs a multi-agent pipeline.

    Returns a PipelineProposal with ordered agent names and confidence.
    Pure heuristic — no LLM call, no async.
    """
    available_names: set[str] = set()
    if available_agents:
        available_names = {a.name for a in available_agents}

    # 1. Find all keyword-matched agents, preserving order of appearance
    matches: list[tuple[int, str]] = []  # (position, agent_name)
    seen: set[str] = set()
    for pattern, agent_names in _KEYWORD_PATTERNS:
        for m in pattern.finditer(prompt):
            for agent in agent_names:
                if agent not in seen:
                    # Skip agents not in the registry
                    if available_names and agent not in available_names:
                        continue
                    matches.append((m.start(), agent))
                    seen.add(agent)

    # Sort by position in prompt (preserves intended order)
    matches.sort(key=lambda x: x[0])
    ordered_agents = [name for _, name in matches]

    if len(ordered_agents) < 2:
        return PipelineProposal(
            should_pipeline=False,
            agents=ordered_agents[:1] if ordered_agents else [],
            confidence=0.9 if ordered_agents else 0.0,
            reason="single agent or no match",
        )

    # 2. Check for sequencing connectives
    has_sequencing = bool(_SEQUENCING_PATTERN.search(prompt))
    has_multi_step = bool(_MULTI_STEP_PATTERN.search(prompt))

    # 3. Score confidence
    confidence = 0.3  # base: 2+ agents matched
    if has_sequencing:
        confidence += 0.35
    if has_multi_step:
        confidence += 0.15
    if len(ordered_agents) >= 3:
        confidence += 0.1
    # Long prompts with multiple agents are more likely pipelines
    if len(prompt) > 200:
        confidence += 0.1
    confidence = min(confidence, 1.0)

    # Pipeline threshold: need connectives OR multi-step markers
    should_pipeline = confidence >= 0.55

    return PipelineProposal(
        should_pipeline=should_pipeline,
        agents=ordered_agents,
        confidence=confidence,
        reason=(
            f"matched {len(ordered_agents)} agents"
            + (", sequencing detected" if has_sequencing else "")
            + (", multi-step" if has_multi_step else "")
        ),
    )
