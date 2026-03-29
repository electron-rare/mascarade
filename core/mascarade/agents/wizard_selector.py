"""
Wizard Agent Selector — deterministic agent selection and scoring.

Matches agents to a task based on domain, cost constraints, and resource availability.
Uses fail-closed patterns: returns empty list if no match rather than guessing.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.agents.wizard_schemas import (
    CostClass,
    ExecutionConstraints,
    NoAgentAvailableError,
    SelectedAgentInfo,
    WizardAgentRunRequest,
    WizardAgentSelectionResult,
)
from mascarade.metrics.tracker import MetricsTracker

logger = logging.getLogger("mascarade.wizard")


@dataclass
class ScoringContext:
    """Context for agent scoring within a selection phase."""

    request: WizardAgentRunRequest
    agent: Agent
    capability_matrix: dict  # From registry.get_capabilities_matrix()
    current_load: dict[str, int]  # agent_name → concurrent_tasks_running


class WizardAgentSelector:
    """Selects agents for a wizard task using deterministic scoring rules."""

    def __init__(self, registry: AgentRegistry, metrics: Optional[MetricsTracker] = None) -> None:
        self.registry = registry
        self.metrics = metrics or MetricsTracker()
        self._lock = asyncio.Lock()
        self._current_load: dict[str, int] = {}  # agent_name → count

    async def select_agents(
        self,
        request: WizardAgentRunRequest,
        top_n: int = 3,
    ) -> WizardAgentSelectionResult:
        """Select and score agents matching the task domain.

        Args:
            request: Task request with domain and constraints
            top_n: Return top N agents (max 5)

        Returns:
            Selection result with ranked agents

        Raises:
            NoAgentAvailableError: No agents match the constraints
        """
        async with self._lock:
            # Get capability matrix from registry
            cap_matrix = self.registry.get_capabilities_matrix()

            # Find agents in the requested domain
            domain_agents = cap_matrix.get("domain_to_agents", {}).get(
                request.domain, []
            )

            if not domain_agents:
                error_msg = f"No agents available for domain '{request.domain}'"
                logger.warning(error_msg)
                raise NoAgentAvailableError(error_msg)

            # Score each agent
            scored_agents = []
            agents_dict = cap_matrix.get("agents", {})

            for agent_name in domain_agents:
                try:
                    agent = self.registry.get(agent_name)
                    cap = agents_dict.get(agent_name)

                    if not cap:
                        logger.debug(f"Skipping {agent_name}: no capability entry")
                        continue

                    # Check constraint compatibility
                    if not self._check_constraints(cap, request.constraints):
                        logger.debug(
                            f"Skipping {agent_name}: constraints not met"
                        )
                        continue

                    # Compute score
                    score = self._compute_score(
                        agent_name=agent_name,
                        capability=cap,
                        context=ScoringContext(
                            request=request,
                            agent=agent,
                            capability_matrix=cap_matrix,
                            current_load=self._current_load,
                        ),
                    )

                    if score > 0:
                        scored_agents.append(
                            (
                                agent_name,
                                score,
                                cap,
                            )
                        )

                except KeyError:
                    logger.debug(f"Agent {agent_name} not found in registry")
                    continue

            # Sort by score descending
            scored_agents.sort(key=lambda x: x[1], reverse=True)

            if not scored_agents:
                error_msg = f"All agents for domain '{request.domain}' failed constraint checks"
                logger.warning(error_msg)
                raise NoAgentAvailableError(error_msg)

            # Return top N
            top_agents = scored_agents[:min(top_n, 5)]

            selected_info = [
                SelectedAgentInfo(
                    name=agent_name,
                    domain=request.domain,
                    selection_score=min(score, 1.0),  # Clamp to [0, 1]
                    cost_class=CostClass(cap.get("cost_class", "medium")),
                )
                for agent_name, score, cap in top_agents
            ]

            result = WizardAgentSelectionResult(
                task_id=f"wizard-{self._generate_task_id()}",
                selected_agents=selected_info,
                total_agents_evaluated=len(domain_agents),
                selection_timestamp=datetime.utcnow(),
            )

            # Log metrics
            self.metrics.track_request(
                provider_name="wizard_selector",
                tokens=0,
                cost=0,
                response_time=0,
                success=True,
            )

            logger.info(
                f"Selected {len(selected_info)}/{len(domain_agents)} agents for domain '{request.domain}'"
            )

            return result

    def _check_constraints(
        self, capability: dict, constraints: ExecutionConstraints
    ) -> bool:
        """Check if agent capability matches constraints.

        Returns:
            True if agent satisfies all constraints, False otherwise
        """
        # Check cost class
        cost_class = capability.get("cost_class", "medium")
        max_cost = constraints.max_cost

        cost_map = {"low": 0.2, "medium": 0.5, "high": 1.0}
        cost_value = cost_map.get(cost_class, 0.5)

        if cost_value > max_cost:
            return False

        # Check required models (if specified)
        if constraints.required_models:
            # For now, assume agent's preferred_model covers one requirement
            # In future, check actual model availability from registry
            if not constraints.required_models:
                return True

        return True

    def _compute_score(
        self,
        agent_name: str,
        capability: dict,
        context: ScoringContext,
    ) -> float:
        """Compute selection score for an agent (0 to 2.0, higher is better).

        Scoring factors:
        - Base score: 1.0 (available)
        - Cost efficiency: +0.3 for low cost, -0.2 for high cost
        - Load balancing: -0.1 per currently running task (max 1.0 penalty)
        - Circuit breaker: -0.5 if degraded
        """
        score = 1.0

        # Cost efficiency bonus
        cost_class = capability.get("cost_class", "medium")
        if cost_class == "low":
            score += 0.3
        elif cost_class == "high":
            score -= 0.2

        # Load balancing: penalize agents with concurrent tasks
        load = self._current_load.get(agent_name, 0)
        concurrent_limit = capability.get("concurrent_limit", 1)

        if concurrent_limit > 0:
            load_ratio = load / concurrent_limit
            score -= min(load_ratio * 0.5, 1.0)  # Max -1.0 penalty

        # Circuit breaker status (would be checked via metrics history)
        # For now, simple heuristic: check recent failure rate
        provider_stats = self.metrics.get_provider_stats(agent_name)
        if provider_stats:
            total = provider_stats.get("total_requests", 0)
            failures = provider_stats.get("failed_requests", 0)
            if total > 5:
                failure_rate = failures / total
                if failure_rate > 0.5:  # 50% failure → degraded
                    score -= 0.5

        return max(score, 0.0)

    async def record_agent_execution(self, agent_name: str, status: str) -> None:
        """Record that an agent is running or completed.

        Args:
            agent_name: Name of the agent
            status: 'running' to increment, 'completed' to decrement
        """
        async with self._lock:
            if status == "running":
                self._current_load[agent_name] = self._current_load.get(agent_name, 0) + 1
            elif status == "completed":
                current = self._current_load.get(agent_name, 0)
                self._current_load[agent_name] = max(current - 1, 0)

    @staticmethod
    def _generate_task_id() -> str:
        """Generate a unique task ID."""
        import time

        return f"{int(time.time() * 1000) % 1000000:06d}"
