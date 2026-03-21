"""A2A (Agent-to-Agent) protocol router.

Implements the A2A protocol (Google / Linux Foundation AAIF) for agent
discovery and inter-agent task delegation.

Endpoints:
  GET  /.well-known/agent.json  — public Agent Card
  POST /a2a/tasks                — submit a task (authenticated)
  GET  /a2a/tasks/{task_id}      — get task status/result (authenticated)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.auth import require_auth
from mascarade.config import settings

logger = logging.getLogger("mascarade.a2a")

# ---------------------------------------------------------------------------
# Task storage (in-memory)
# ---------------------------------------------------------------------------

@dataclass
class A2ATask:
    """Represents a single A2A task through its lifecycle."""

    id: str
    skill_id: str
    status: str  # submitted | working | completed | failed | cancelled
    input_text: str
    output_text: str | None = None
    created_at: str = ""
    updated_at: str = ""


_tasks: dict[str, A2ATask] = {}
_tasks_lock = asyncio.Lock()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_task(task_id: str) -> A2ATask:
    async with _tasks_lock:
        task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class TaskInput(BaseModel):
    text: str = Field(..., min_length=1, description="Input text for the task")


class TaskSubmitRequest(BaseModel):
    skill_id: str = Field(..., min_length=1, description="Skill (agent) to route the task to")
    input: TaskInput


class TaskResponse(BaseModel):
    id: str
    skill_id: str
    status: str
    input_text: str
    output_text: str | None = None
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Public router — no auth (Agent Card discovery)
public_router = APIRouter(tags=["a2a"])

# Authenticated router — requires API key
authed_router = APIRouter(
    prefix="/a2a",
    dependencies=[Depends(require_auth)],
    tags=["a2a"],
)


@public_router.get("/.well-known/agent.json")
async def agent_card(request: Request):
    """Return the A2A Agent Card for discovery.

    Dynamically builds the skills list from the AgentRegistry and
    SkillRegistry attached to the running application.
    """
    skills: list[dict] = []

    # Populate from AgentRegistry (agents as high-level skills)
    if hasattr(request.app.state, "registry") and request.app.state.registry is not None:
        for agent in request.app.state.registry.list():
            skills.append({
                "id": agent.name,
                "name": agent.name,
                "description": agent.description or "",
                "tags": agent.tools[:5] if agent.tools else [],
            })

    # Populate from SkillRegistry (v2 fine-grained skills)
    if hasattr(request.app.state, "skill_registry") and request.app.state.skill_registry is not None:
        for skill in request.app.state.skill_registry.list():
            skills.append({
                "id": skill.name,
                "name": skill.name,
                "description": skill.description or "",
                "tags": [skill.category] if skill.category else [],
            })

    # Determine capabilities from settings
    capabilities = {
        "streaming": True,
        "pushNotifications": False,
        "stateTransitionHistory": True,
    }
    if settings.p2p_enabled:
        capabilities["p2p"] = True
    if settings.cluster_enabled:
        capabilities["cluster"] = True

    return {
        "name": settings.a2a_agent_name,
        "description": "Multi-agent LLM orchestration engine",
        "url": settings.a2a_agent_url or str(request.base_url).rstrip("/"),
        "version": "0.1.0",
        "capabilities": capabilities,
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": skills,
    }


@authed_router.post("/tasks", response_model=TaskResponse, status_code=201)
async def submit_task(req: TaskSubmitRequest, request: Request):
    """Submit an A2A task routed to the specified skill/agent."""
    if not settings.a2a_enabled:
        raise HTTPException(status_code=503, detail="A2A protocol is disabled")

    # Validate that the skill/agent exists
    agent_found = False
    if hasattr(request.app.state, "registry") and request.app.state.registry is not None:
        if req.skill_id in request.app.state.registry:
            agent_found = True
    if not agent_found and hasattr(request.app.state, "skill_registry") and request.app.state.skill_registry is not None:
        if req.skill_id in request.app.state.skill_registry:
            agent_found = True

    if not agent_found:
        raise HTTPException(status_code=404, detail=f"Skill '{req.skill_id}' not found")

    now = _utcnow_iso()
    task = A2ATask(
        id=str(uuid.uuid4()),
        skill_id=req.skill_id,
        status="submitted",
        input_text=req.input.text,
        created_at=now,
        updated_at=now,
    )
    async with _tasks_lock:
        _tasks[task.id] = task

    # Fire-and-forget background execution
    asyncio.create_task(_execute_task(task, request))

    return TaskResponse(**asdict(task))


@authed_router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """Return the current status and result of an A2A task."""
    if not settings.a2a_enabled:
        raise HTTPException(status_code=503, detail="A2A protocol is disabled")
    task = await _get_task(task_id)
    return TaskResponse(**asdict(task))


# ---------------------------------------------------------------------------
# Background execution
# ---------------------------------------------------------------------------

async def _execute_task(task: A2ATask, request: Request) -> None:
    """Run the task against the orchestrator in the background."""
    try:
        async with _tasks_lock:
            task.status = "working"
            task.updated_at = _utcnow_iso()

        orchestrator = getattr(request.app.state, "orchestrator", None)
        if orchestrator is None:
            raise RuntimeError("Orchestrator not available")

        result = await orchestrator.run(
            agent_name=task.skill_id,
            user_message=task.input_text,
        )

        async with _tasks_lock:
            task.status = "completed"
            # result may be an LLMResponse or a dict — extract text
            if hasattr(result, "text"):
                task.output_text = result.text
            elif isinstance(result, dict):
                task.output_text = result.get("text", str(result))
            else:
                task.output_text = str(result)
            task.updated_at = _utcnow_iso()

    except Exception as exc:
        logger.error("A2A task %s failed: %s", task.id, exc, exc_info=True)
        async with _tasks_lock:
            task.status = "failed"
            task.output_text = str(exc)
            task.updated_at = _utcnow_iso()
