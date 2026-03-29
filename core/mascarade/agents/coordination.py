"""Coordination engine for multi-agent execution workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mascarade.agents.registry import AgentRegistry
from mascarade.orchestrator.engine import ExecutionMode, Orchestrator


@dataclass(slots=True)
class CoordinationContext:
    """Runtime context for a coordination request."""

    prompt: str
    project_id: str | None = None
    federation_scope: list[str] = field(default_factory=list)
    knowledge_scope: str = "project"


@dataclass(slots=True)
class CoordinationRequest:
    """Request envelope used by CoordinationEngine."""

    task: str
    domain: str | None = None
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    agent_names: list[str] | None = None
    require_planning: bool = False


@dataclass(slots=True)
class CoordinationResult:
    """Normalized result for sequential/parallel/pipeline coordination."""

    mode: ExecutionMode
    agents_used: list[str]
    outputs: list[dict[str, Any]]


_DOMAIN_CLUSTER_MAP: dict[str, str] = {
    "kicad": "electronics",
    "spice": "electronics",
    "iot": "electronics",
    "embedded": "electronics",
    "platformio": "electronics",
    "ops": "ops",
    "security": "ops",
    "code": "code",
}


class CoordinationEngine:
    """Select agents and execute them through the Orchestrator."""

    def __init__(
        self,
        registry: AgentRegistry,
        *,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        self._registry = registry
        self._orchestrator = orchestrator or Orchestrator(registry=registry)

    def select_agents(self, request: CoordinationRequest) -> list[str]:
        """Select agents based on explicit list, domain cluster, and task fallback."""
        if request.agent_names:
            return self._validate_explicit_agents(request.agent_names)

        selected: list[str] = []
        domain = (request.domain or "").strip().lower()
        if domain:
            cluster = _DOMAIN_CLUSTER_MAP.get(domain)
            if cluster:
                selected.extend(a.name for a in self._registry.find_by_cluster(cluster))

        if not selected:
            best = self._registry.find_best_for(request.task)
            if best is not None:
                selected.append(best.name)

        if not selected and "agent-zero" in self._registry:
            selected.append("agent-zero")

        if not selected:
            # Deterministic final fallback: first agent by sorted name.
            sorted_names = sorted(agent.name for agent in self._registry.list())
            if sorted_names:
                selected.append(sorted_names[0])

        return _dedupe_keep_order(selected)

    async def run_sequential(
        self,
        agent_names: list[str],
        context: CoordinationContext,
    ) -> CoordinationResult:
        run = await self._orchestrator.run(
            agent_names,
            context.prompt,
            mode=ExecutionMode.SEQUENTIAL,
            project_id=context.project_id,
            federation_scope=context.federation_scope,
            knowledge_scope=context.knowledge_scope,
        )
        return self._to_result(run, ExecutionMode.SEQUENTIAL)

    async def run_parallel(
        self,
        agent_names: list[str],
        context: CoordinationContext,
    ) -> CoordinationResult:
        run = await self._orchestrator.run(
            agent_names,
            context.prompt,
            mode=ExecutionMode.PARALLEL,
            project_id=context.project_id,
            federation_scope=context.federation_scope,
            knowledge_scope=context.knowledge_scope,
        )
        return self._to_result(run, ExecutionMode.PARALLEL)

    async def coordinate(
        self,
        request: CoordinationRequest,
        context: CoordinationContext,
    ) -> CoordinationResult:
        """Entry point that selects agents and dispatches by execution mode."""
        agents = self.select_agents(request)
        if not agents:
            return CoordinationResult(mode=request.mode, agents_used=[], outputs=[])

        if request.mode == ExecutionMode.SEQUENTIAL:
            return await self.run_sequential(agents, context)

        if request.mode == ExecutionMode.PARALLEL:
            return await self.run_parallel(agents, context)

        # Pipeline mode (or explicit planning need) is delegated to Orchestrator.
        run = await self._orchestrator.run(
            agents,
            context.prompt,
            mode=ExecutionMode.PIPELINE,
            project_id=context.project_id,
            federation_scope=context.federation_scope,
            knowledge_scope=context.knowledge_scope,
        )
        return self._to_result(run, ExecutionMode.PIPELINE)

    def _validate_explicit_agents(self, names: list[str]) -> list[str]:
        valid: list[str] = []
        for name in names:
            if name in self._registry:
                valid.append(name)
        return _dedupe_keep_order(valid)

    @staticmethod
    def _to_result(run: Any, mode: ExecutionMode) -> CoordinationResult:
        outputs: list[dict[str, Any]] = []
        for item in getattr(run, "results", []):
            outputs.append(
                {
                    "agent_name": item.agent_name,
                    "content": getattr(item.response, "content", ""),
                    "provider": getattr(item.response, "provider", None),
                    "model": getattr(item.response, "model", None),
                    "error": item.error,
                }
            )
        return CoordinationResult(
            mode=mode,
            agents_used=[item["agent_name"] for item in outputs],
            outputs=outputs,
        )


def _dedupe_keep_order(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out
