"""Agent de base — brique fondamentale de l'orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from mascarade.observability.langfuse import (
    create_trace,
    flush_langfuse,
    get_trace_id,
)
from mascarade.router import Router
from mascarade.router.providers.base import LLMResponse
from mascarade.router.router import Strategy

if TYPE_CHECKING:
    from mascarade.agents.registry import AgentRegistry
    from mascarade.agents.skill_registry import SkillRegistry

logger = logging.getLogger("mascarade.agents")


# ---------------------------------------------------------------------------
# Gate system — execution checkpoints for quality/safety
# ---------------------------------------------------------------------------


class GateStatus(str, Enum):
    """Gate evaluation result."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Gate:
    """A checkpoint that must pass before or after agent execution.

    Gates can enforce pre-conditions (input validation, authorization)
    or post-conditions (output quality, safety review).
    """

    name: str
    description: str = ""
    phase: str = "pre"  # "pre" (before execution) or "post" (after execution)
    required: bool = True  # if True, failure blocks execution
    check: str = ""  # callable name or expression to evaluate
    status: GateStatus = GateStatus.PENDING


@dataclass
class EvidenceRecord:
    """Tracks an agent execution with evidence for audit/compliance."""

    run_id: str
    agent_name: str
    timestamp: str = ""
    input_hash: str = ""
    output_hash: str = ""
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class Agent:
    """Un agent spécialisé avec son propre contexte et comportement."""

    name: str
    description: str
    system_prompt: str
    preferred_provider: str | None = None
    preferred_model: str | None = None
    preferred_role: str | None = None
    strategy: Strategy = Strategy.BEST
    routing_policy: str = "auto"
    tools: list[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096
    skills: list[str] = field(default_factory=list)  # assigned skill names
    category: str | None = None  # grouping: domain, code, creative, etc.
    retry_config: dict | None = None
    prompt_versions: list[dict] = field(default_factory=list)
    gates: list[Gate] = field(default_factory=list)  # execution gates
    evidence_refs: list[str] = field(default_factory=list)  # evidence doc refs
    capabilities: list[str] = field(default_factory=list)  # e.g. ["code", "pcb", "review"]
    cluster: str | None = None  # domain cluster: general, code, electronics, ops, creative

    def get_enhanced_system_prompt(self, skill_registry: SkillRegistry) -> str:
        """Build system prompt enhanced with assigned skills.

        Concatenates the agent's base system_prompt with instruction fragments
        from all assigned and enabled skills.
        """
        parts = [self.system_prompt]
        for skill_name in self.skills:
            try:
                skill = skill_registry.get(skill_name)
            except KeyError:
                continue
            if skill.enabled and skill.instruction:
                parts.append(skill.instruction)
        return "\n\n".join(parts)

    def build_send_payload(
        self,
        prompt: str,
        *,
        context: list[dict] | None = None,
        skill_registry: SkillRegistry | None = None,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> dict[str, object]:
        messages = list(context) if context else []
        messages.append({"role": "user", "content": prompt})
        return {
            "messages": messages,
            "strategy": self.strategy,
            "routing_policy": self.routing_policy,
            "provider": self.preferred_provider,
            "model": self.preferred_model,
            "system": self._resolve_system_prompt(skill_registry),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "project_id": project_id,
            "federation_scope": list(federation_scope or []),
            "knowledge_scope": knowledge_scope,
        }

    def _resolve_system_prompt(self, skill_registry: SkillRegistry | None = None) -> str:
        """Return the effective system prompt, enhanced with skills if available."""
        if skill_registry and self.skills:
            return self.get_enhanced_system_prompt(skill_registry)
        return self.system_prompt

    # ------------------------------------------------------------------
    # Gate checking
    # ------------------------------------------------------------------

    def check_gates(self, phase: str = "pre") -> tuple[bool, list[str]]:
        """Evaluate gates for the given phase.

        Returns (all_passed, list_of_failed_gate_names).
        Non-required gates that fail are logged but don't block.
        """
        failed: list[str] = []
        for gate in self.gates:
            if gate.phase != phase:
                continue
            # Built-in gate checks
            passed = self._evaluate_gate(gate)
            gate.status = GateStatus.PASSED if passed else GateStatus.FAILED
            if not passed:
                if gate.required:
                    failed.append(gate.name)
                else:
                    logger.warning(
                        "Agent %s: optional gate '%s' failed (phase=%s)",
                        self.name,
                        gate.name,
                        phase,
                    )
        return len(failed) == 0, failed

    def _evaluate_gate(self, gate: Gate) -> bool:
        """Evaluate a single gate. Override for custom gate logic."""
        if not gate.check:
            return True  # no check expression = auto-pass
        # Built-in checks
        if gate.check == "has_system_prompt":
            return bool(self.system_prompt.strip())
        if gate.check == "has_skills":
            return len(self.skills) > 0
        if gate.check == "has_tools":
            return len(self.tools) > 0
        if gate.check == "is_configured":
            return self.preferred_provider is not None
        # Unknown check — pass by default
        logger.debug("Unknown gate check '%s' on agent %s", gate.check, self.name)
        return True

    def reset_gates(self) -> None:
        """Reset all gates to pending status."""
        for gate in self.gates:
            gate.status = GateStatus.PENDING

    def create_evidence(
        self, run_id: str, duration_ms: float = 0.0, **metadata: object
    ) -> EvidenceRecord:
        """Create an evidence record from the current gate state."""
        return EvidenceRecord(
            run_id=run_id,
            agent_name=self.name,
            timestamp=datetime.now(UTC).isoformat(),
            gates_passed=[g.name for g in self.gates if g.status == GateStatus.PASSED],
            gates_failed=[g.name for g in self.gates if g.status == GateStatus.FAILED],
            duration_ms=duration_ms,
            metadata=dict(metadata),
        )

    async def run(
        self,
        prompt: str,
        *,
        router: Router,
        context: list[dict] | None = None,
        registry: AgentRegistry | None = None,
        skill_registry: SkillRegistry | None = None,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
        system_override: str | None = None,
    ) -> LLMResponse:
        """Exécuter l'agent avec un prompt donné."""
        # Set up Langfuse trace for this agent invocation (opt-in, no-op if disabled)
        if get_trace_id() is None:
            create_trace(
                name=f"agent/{self.name}",
                metadata={"agent": self.name, "strategy": self.strategy},
                tags=["agent"],
            )

        system = system_override or self._resolve_system_prompt(skill_registry)
        messages = list(context) if context else []
        messages.append({"role": "user", "content": prompt})
        response = await router.send(
            messages,
            strategy=self.strategy,
            routing_policy=self.routing_policy,
            provider=self.preferred_provider,
            model=self.preferred_model,
            system=system,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )
        flush_langfuse()
        return response

    async def run_with_history(
        self,
        messages: list[dict],
        *,
        router: Router,
        registry: AgentRegistry | None = None,
        skill_registry: SkillRegistry | None = None,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
    ) -> LLMResponse:
        """Exécuter l'agent avec un historique de messages complet."""
        # Set up Langfuse trace for this agent invocation (opt-in, no-op if disabled)
        if get_trace_id() is None:
            create_trace(
                name=f"agent/{self.name}",
                metadata={"agent": self.name, "strategy": self.strategy},
                tags=["agent"],
            )

        system = self._resolve_system_prompt(skill_registry)
        response = await router.send(
            messages,
            strategy=self.strategy,
            routing_policy=self.routing_policy,
            provider=self.preferred_provider,
            model=self.preferred_model,
            system=system,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )
        flush_langfuse()
        return response
