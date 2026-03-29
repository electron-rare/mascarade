"""Wizard Agents Management endpoints (core)."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, StatusCode
from pydantic import BaseModel, Field

from mascarade.agents.registry import AgentRegistry
from mascarade.agents.wizard_orchestrator import WizardOrchestrator
from mascarade.agents.wizard_schemas import (
    ExecutionMode,
    NoAgentAvailableError,
    WizardAgentCapabilityMatrix,
    WizardAgentRunRequest,
    WizardRunResult,
    WizardRunStatusResponse,
    WizardRunStatus,
)
from mascarade.agents.wizard_selector import WizardAgentSelector
from mascarade.agents.wizard_storage import get_wizard_storage
from mascarade.auth import require_auth
from mascarade.metrics.tracker import MetricsTracker

logger = logging.getLogger("mascarade.wizard")

# Router setup
router = APIRouter(
    prefix="/api/wizard",
    tags=["wizard"],
)

# Singleton dependencies
_registry: Optional[AgentRegistry] = None
_selector: Optional[WizardAgentSelector] = None
_orchestrator: Optional[WizardOrchestrator] = None
_metrics: Optional[MetricsTracker] = None


def get_dependencies():
    """Initialize singletons if needed."""
    global _registry, _selector, _orchestrator, _metrics

    if _registry is None:
        _registry = AgentRegistry()
        _metrics = MetricsTracker()
        _selector = WizardAgentSelector(_registry, _metrics)
        _orchestrator = WizardOrchestrator(_registry, _metrics)

    return _registry, _selector, _orchestrator


# --- Models ---


class HealthResponse(BaseModel):
    """Health check response for wizard service."""

    status: str
    agents_available: int
    failed_selections_5m: int
    avg_latency_ms: float


# --- Routes ---


@router.post(
    "/run",
    response_model=WizardRunResult,
    status_code=201,
    summary="Run wizard agents for a task",
)
async def run_wizard(
    request: WizardAgentRunRequest,
) -> WizardRunResult:
    """Execute wizard agent selection and orchestration.

    1. Select agents matching the task domain and constraints
    2. Execute selected agents (sequential or parallel)
    3. Aggregate results and return final analysis

    Returns:
        WizardRunResult with all agent results, metrics, and aggregated analysis
    """
    registry, selector, orchestrator = get_dependencies()
    storage = await get_wizard_storage()

    try:
        # Phase 1: Select agents
        logger.info(f"Selecting agents for domain '{request.domain}'")
        selection_result = await selector.select_agents(request, top_n=3)

        # Create run record in database
        run_id = await storage.create_run(
            task_id=selection_result.task_id,
            execution_mode=request.execution_mode.value,
            initial_status=WizardRunStatus.RUNNING.value,
        )

        # Convert selected agents to execution format
        selected_agents = [
            {"name": agent.name, "cost_class": agent.cost_class.value}
            for agent in selection_result.selected_agents
        ]

        # Phase 2: Orchestrate execution
        logger.info(
            f"Executing {len(selected_agents)} agents (mode={request.execution_mode.value})"
        )
        result = await orchestrator.execute(
            task_id=selection_result.task_id,
            selected_agents=selected_agents,
            task_description=request.task,
            task_context=request.context,
            execution_mode=request.execution_mode,
            timeout_seconds=request.timeout_seconds,
            continue_on_error=request.continue_on_error,
            fail_on_partial=request.fail_on_partial,
        )

        # Phase 3: Persist result
        await storage.save_run(result)
        logger.info(
            f"Wizard run {result.task_id} completed: {result.status.value}"
        )

        return result

    except NoAgentAvailableError as e:
        logger.error(f"No agents available: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Wizard execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/status/{task_id}",
    response_model=WizardRunStatusResponse,
    summary="Get status of a wizard run",
)
async def get_wizard_status(
    task_id: str = Query(..., min_length=1, max_length=256),
) -> WizardRunStatusResponse:
    """Retrieve status and progress of a wizard task execution.

    Used for polling during long-running executions.

    Args:
        task_id: Unique task identifier from run response

    Returns:
        Status with progress_percent (0-100) and partial results
    """
    storage = await get_wizard_storage()

    run = await storage.get_run(task_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {task_id} not found")

    return WizardRunStatusResponse(
        task_id=task_id,
        status=WizardRunStatus(run["status"]),
        progress_percent=run.get("progress_percent", 0),
        results=None,  # Could include partial results
        error=run.get("error_reason"),
        last_update=run.get("completed_at") or run.get("created_at"),
    )


@router.get(
    "/agents",
    response_model=WizardAgentCapabilityMatrix,
    summary="List available agents and capabilities",
)
async def list_wizard_agents() -> WizardAgentCapabilityMatrix:
    """Get the agent capabilities matrix for task selection.

    Returns information about all available agents:
    - Agent capabilities (domain, cost_class, concurrent_limit)
    - Reverse mapping (domain → agent names)
    - Total agent count

    Returns:
        Agent capability matrix
    """
    registry, _, _ = get_dependencies()

    cap_matrix = registry.get_capabilities_matrix()

    return WizardAgentCapabilityMatrix(
        agents=cap_matrix.get("agents", {}),
        domain_to_agents=cap_matrix.get("domain_to_agents", {}),
        total_agents=cap_matrix.get("total_agents", 0),
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check for wizard service",
)
async def wizard_health() -> HealthResponse:
    """Wizard service health status.

    Returns:
        Health status with agents available and recent error metrics
    """
    registry, _, _ = get_dependencies()
    metrics = _metrics

    cap_matrix = registry.get_capabilities_matrix()
    total_agents = cap_matrix.get("total_agents", 0)

    # Compute recent failure rate (placeholder)
    stats = metrics.get_summary()
    failed_selections = 0  # Would query from storage for last 5 minutes
    avg_latency = stats.get("avg_response_time_ms", 0) if stats else 0

    return HealthResponse(
        status="healthy" if total_agents > 0 else "degraded",
        agents_available=total_agents,
        failed_selections_5m=failed_selections,
        avg_latency_ms=avg_latency,
    )
