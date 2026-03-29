"""FastAPI router for multi-agent coordination workflows."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from mascarade.agents.coordination import (
    CoordinationContext,
    CoordinationEngine,
    CoordinationRequest,
)
from mascarade.auth import require_auth
from mascarade.orchestrator.engine import ExecutionMode

router = APIRouter(
    prefix="/v1/api/coordination",
    tags=["coordination"],
    dependencies=[Depends(require_auth)],
)

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


class CoordinationRunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=50000)
    domain: str | None = Field(default=None, max_length=64)
    mode: Literal["sequential", "parallel", "pipeline"] = "sequential"
    agent_names: list[str] | None = None
    project_id: str | None = Field(default=None, max_length=256)
    federation_scope: list[str] | None = None
    knowledge_scope: Literal["project", "federated"] = "project"
    require_planning: bool = False


class CoordinationRunResponse(BaseModel):
    task_id: str
    status: Literal["completed"]
    mode: str
    agents_used: list[str]
    outputs: list[dict]


def _ensure_runtime_state(request: Request) -> None:
    if not hasattr(request.app.state, "registry"):
        raise HTTPException(status_code=503, detail="Agent registry not initialized")
    if not hasattr(request.app.state, "orchestrator"):
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")


def _coordination_store(request: Request) -> dict[str, dict]:
    if not hasattr(request.app.state, "coordination_runs"):
        request.app.state.coordination_runs = {}
    return request.app.state.coordination_runs


@router.post("/run", response_model=CoordinationRunResponse)
async def run_coordination(body: CoordinationRunRequest, request: Request) -> CoordinationRunResponse:
    _ensure_runtime_state(request)

    engine = CoordinationEngine(
        request.app.state.registry,
        orchestrator=request.app.state.orchestrator,
    )

    req = CoordinationRequest(
        task=body.task,
        domain=body.domain,
        mode=ExecutionMode(body.mode),
        agent_names=body.agent_names,
        require_planning=body.require_planning,
    )
    ctx = CoordinationContext(
        prompt=body.task,
        project_id=body.project_id,
        federation_scope=list(body.federation_scope or []),
        knowledge_scope=body.knowledge_scope,
    )

    try:
        result = await engine.coordinate(req, ctx)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    task_id = uuid4().hex
    payload = {
        "task_id": task_id,
        "status": "completed",
        "mode": result.mode.value,
        "agents_used": result.agents_used,
        "outputs": result.outputs,
    }

    _coordination_store(request)[task_id] = payload
    return CoordinationRunResponse(**payload)


@router.get("/status/{task_id}")
async def coordination_status(task_id: str, request: Request) -> dict:
    store = _coordination_store(request)
    if task_id not in store:
        raise HTTPException(status_code=404, detail=f"Coordination task '{task_id}' not found")
    return store[task_id]


@router.get("/agents")
async def coordination_agents(
    request: Request,
    domain: str | None = Query(default=None, max_length=64),
    cluster: str | None = Query(default=None, max_length=64),
    capability: str | None = Query(default=None, max_length=64),
) -> dict:
    if not hasattr(request.app.state, "registry"):
        raise HTTPException(status_code=503, detail="Agent registry not initialized")

    registry = request.app.state.registry
    agents = registry.list()

    if domain:
        mapped_cluster = _DOMAIN_CLUSTER_MAP.get(domain.strip().lower())
        if mapped_cluster is None:
            agents = []
        else:
            agents = [a for a in agents if a.cluster == mapped_cluster]

    if cluster:
        agents = [a for a in agents if a.cluster == cluster]

    if capability:
        agents = [a for a in agents if capability in (a.capabilities or [])]

    items = [
        {
            "name": a.name,
            "description": a.description,
            "cluster": a.cluster,
            "capabilities": a.capabilities,
            "builtin": registry.is_builtin(a.name),
        }
        for a in agents
    ]

    return {"agents": items, "total": len(items)}
