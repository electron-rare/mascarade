"""Agent management endpoints."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from mascarade.agents import Agent
from mascarade.agents.prompt_versioning import PromptHistory, PromptVersion
from mascarade.auth import require_auth
from mascarade.project_scope import normalize_scope
from mascarade.router.router import Strategy

router = APIRouter(prefix="/v1/api", dependencies=[Depends(require_auth)], tags=["agents"])


# --- Models ---


RoutingPolicy = Literal["auto", "strong", "cheap", "fast"]


class Message(BaseModel):
    """A chat message with role and content."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=100_000)


class AgentCreate(BaseModel):
    """Request model for creating a new agent."""

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=1000)
    system_prompt: str = Field(max_length=50_000)
    preferred_provider: str | None = Field(default=None, max_length=50)
    preferred_model: str | None = Field(default=None, max_length=100)
    preferred_role: str | None = Field(default=None, max_length=100)
    strategy: Strategy = Strategy.ROUTELLM
    routing_policy: RoutingPolicy = "auto"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)


class AgentUpdate(BaseModel):
    """Request model for updating an existing agent."""

    description: str = Field(max_length=1000)
    system_prompt: str = Field(max_length=50_000)
    preferred_provider: str | None = Field(default=None, max_length=50)
    preferred_model: str | None = Field(default=None, max_length=100)
    preferred_role: str | None = Field(default=None, max_length=100)
    strategy: Strategy = Strategy.ROUTELLM
    routing_policy: RoutingPolicy = "auto"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)
    version_note: str | None = Field(default=None, max_length=500)


class SendRequest(BaseModel):
    """Request model for running an agent with messages."""

    messages: list[Message] = Field(max_length=200)
    strategy: Strategy = Strategy.BEST
    routing_policy: RoutingPolicy = "auto"
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=100)
    system: str | None = Field(default=None, max_length=10_000)
    response_format: dict | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)
    project_id: str | None = Field(default=None, max_length=256)
    federation_scope: list[str] | None = None
    knowledge_scope: Literal["project", "federated"] = "project"


# --- Helper functions ---


def hash_api_key(key: str) -> str:
    """Hash API key for author tracking (returns first 8 chars of SHA-256)."""
    if not key:
        return ""
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def _serialize_agent(agent: Agent, request: Request) -> dict[str, object]:
    """
    Serialize an agent to a dictionary for API response.

    Args:
        agent: Agent instance to serialize
        request: FastAPI request object for accessing registry state

    Returns:
        Dictionary containing agent configuration and metadata
    """
    return {
        "name": agent.name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "preferred_provider": agent.preferred_provider,
        "preferred_model": agent.preferred_model,
        "preferred_role": agent.preferred_role,
        "strategy": agent.strategy.value,
        "routing_policy": agent.routing_policy,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "builtin": request.app.state.registry.is_builtin(agent.name),
    }


# --- Endpoints ---


@router.post("/agents")
async def create_agent(req: AgentCreate, request: Request):
    """
    Create a new agent with the specified configuration.

    Args:
        req: Agent creation parameters including name, description, and routing settings
        request: FastAPI request object for accessing app state

    Returns:
        Serialized agent object with all configuration details

    Raises:
        HTTPException: If agent with the same name already exists
    """
    if req.name in request.app.state.registry:
        raise HTTPException(
            status_code=409,
            detail=f"Agent '{req.name}' already exists",
        )

    agent = Agent(
        name=req.name,
        description=req.description,
        system_prompt=req.system_prompt,
        preferred_provider=req.preferred_provider,
        preferred_model=req.preferred_model,
        preferred_role=req.preferred_role,
        strategy=req.strategy,
        routing_policy=req.routing_policy,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    request.app.state.registry.register(agent)
    request.app.state.registry.save()
    return _serialize_agent(agent, request)


@router.get("/v1/agents")
async def list_agents(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
):
    """
    List all registered agents in the system with pagination.

    Args:
        request: FastAPI request object for accessing app state
        limit: Maximum number of agents to return (1-200, default 50)
        offset: Number of agents to skip (default 0)

    Returns:
        Dictionary with agents list and pagination metadata
    """
    all_agents = request.app.state.registry.list()
    total = len(all_agents)
    page = all_agents[offset : offset + limit]
    return {
        "agents": [_serialize_agent(agent, request) for agent in page],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/v1/agents/{name}")
async def get_agent(name: str, request: Request):
    """
    Get a specific agent by name.

    Args:
        name: Agent name to retrieve
        request: FastAPI request object for accessing app state

    Returns:
        Serialized agent object with all configuration details

    Raises:
        HTTPException: If agent with the specified name is not found (404)
    """
    try:
        agent = request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
    return _serialize_agent(agent, request)


@router.put("/agents/{name}")
async def update_agent(name: str, req: AgentUpdate, request: Request):
    """
    Update an existing agent's configuration.

    This endpoint supports prompt versioning - when the system_prompt is changed,
    a new version is automatically created and tracked.

    Args:
        name: Agent name to update
        req: Updated agent configuration including optional version note
        request: FastAPI request object for accessing app state

    Returns:
        Serialized agent object with updated configuration

    Raises:
        HTTPException: If agent is not found (404) or is a built-in agent (403)
    """
    try:
        agent = request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
    if request.app.state.registry.is_builtin(name):
        raise HTTPException(
            status_code=403,
            detail="Built-in agents are read-only; create a dynamic agent from the UI to edit routing.",
        )

    # Check if system_prompt is changing
    old_system_prompt = agent.system_prompt
    system_prompt_changed = old_system_prompt != req.system_prompt

    # Update agent fields
    agent.description = req.description
    agent.system_prompt = req.system_prompt
    agent.preferred_provider = req.preferred_provider
    agent.preferred_model = req.preferred_model
    agent.preferred_role = req.preferred_role
    agent.strategy = req.strategy
    agent.routing_policy = req.routing_policy
    agent.temperature = req.temperature
    agent.max_tokens = req.max_tokens

    # Create version if system_prompt changed
    if system_prompt_changed:
        # Get API key from request headers for author tracking
        auth_header = request.headers.get("Authorization", "")
        api_key = ""
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        author_hash = hash_api_key(api_key)

        # Create PromptHistory and load existing versions
        prompt_history = PromptHistory(storage_path=None)
        prompt_history._versions = [PromptVersion(**v) for v in agent.prompt_versions]

        # Add new version
        prompt_history.add_version(
            content=req.system_prompt,
            author_hash=author_hash,
            note=req.version_note,
        )

        # Update agent's prompt_versions
        agent.prompt_versions = [asdict(v) for v in prompt_history._versions]

    request.app.state.registry.save()
    return _serialize_agent(agent, request)


@router.delete("/agents/{name}")
async def delete_agent(name: str, request: Request):
    """
    Delete an agent from the registry.

    Args:
        name: Agent name to delete
        request: FastAPI request object for accessing app state

    Returns:
        Success message confirming deletion

    Raises:
        HTTPException: If agent is not found (404) or is a built-in agent (403)
    """
    try:
        request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
    if request.app.state.registry.is_builtin(name):
        raise HTTPException(
            status_code=403,
            detail="Built-in agents are read-only and cannot be deleted.",
        )

    request.app.state.registry.remove(name)
    request.app.state.registry.save()
    return {"message": f"Agent '{name}' deleted successfully"}


@router.post("/agents/{name}/run")
async def run_agent(name: str, req: SendRequest, request: Request):
    """
    Run an agent with the provided messages.

    Args:
        name: Agent name to run
        req: Request containing messages and optional routing parameters
        request: FastAPI request object for accessing app state

    Returns:
        Dictionary containing response content, model used, provider, and usage statistics

    Raises:
        HTTPException: If agent is not found (404) or no messages provided (400)
    """
    if not req.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    try:
        agent = request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None

    try:
        normalized_project, normalized_federation, normalized_scope = normalize_scope(
            project_id=req.project_id,
            federation_scope=req.federation_scope,
            knowledge_scope=req.knowledge_scope,
            require_project_id=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    messages = [m.model_dump() for m in req.messages]
    prompt = messages[-1]["content"]
    context = messages[:-1] if len(messages) > 1 else None
    try:
        response = await agent.run(
            prompt,
            router=request.app.state.router,
            context=context,
            skill_registry=getattr(request.app.state, "skill_registry", None),
            project_id=normalized_project,
            federation_scope=normalized_federation,
            knowledge_scope=normalized_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


@router.post("/triage")
async def triage_request(req: SendRequest, request: Request):
    """Triage a request — auto-select agent or pipeline.

    Analyzes the prompt and decides whether to use a single agent or
    chain multiple agents in a pipeline.  Uses fast heuristics first,
    falls back to a cheap LLM classification call.

    Returns the agent response(s) directly.
    """
    if not req.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    from mascarade.agents.triage import TriageAgent

    triage = TriageAgent(request.app.state.registry)
    messages = [m.model_dump() for m in req.messages]
    prompt = messages[-1]["content"]
    context = messages[:-1] if len(messages) > 1 else None

    try:
        normalized_project, normalized_federation, normalized_scope = normalize_scope(
            project_id=req.project_id,
            federation_scope=req.federation_scope,
            knowledge_scope=req.knowledge_scope,
            require_project_id=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        decision = await triage.triage(
            prompt,
            router=request.app.state.router,
            skill_registry=getattr(request.app.state, "skill_registry", None),
            project_id=normalized_project,
            federation_scope=normalized_federation,
            knowledge_scope=normalized_scope,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Triage failed: {exc}") from exc

    # Execute based on decision
    try:
        if decision.mode == "pipeline" and len(decision.agents) > 1:
            # Pipeline execution via orchestrator
            orchestrator = getattr(request.app.state, "orchestrator", None)
            if orchestrator:
                run = await orchestrator.run(
                    agent_names=decision.agents,
                    prompt=prompt,
                    mode="pipeline",
                    project_id=normalized_project,
                    federation_scope=normalized_federation,
                    knowledge_scope=normalized_scope,
                )
                return {
                    "triage": {
                        "mode": decision.mode,
                        "agents": decision.agents,
                        "reason": decision.reason,
                        "confidence": decision.confidence,
                        "source": decision.source,
                    },
                    "results": [
                        {
                            "agent": r.agent_name,
                            "content": r.response.content,
                            "model": r.response.model,
                            "provider": r.response.provider,
                            "step": r.step,
                        }
                        for r in run.results
                    ],
                }

        # Single agent execution
        agent_name = decision.agents[0]
        agent = request.app.state.registry.get(agent_name)
        response = await agent.run(
            prompt,
            router=request.app.state.router,
            context=context,
            skill_registry=getattr(request.app.state, "skill_registry", None),
            project_id=normalized_project,
            federation_scope=normalized_federation,
            knowledge_scope=normalized_scope,
        )
        return {
            "triage": {
                "mode": decision.mode,
                "agents": decision.agents,
                "reason": decision.reason,
                "confidence": decision.confidence,
                "source": decision.source,
            },
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/triage/analyze")
async def triage_analyze(req: SendRequest, request: Request):
    """Dry-run triage — returns the decision without executing agents.

    Useful for debugging routing decisions.
    """
    if not req.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    from mascarade.agents.triage import TriageAgent

    triage = TriageAgent(request.app.state.registry)
    messages = [m.model_dump() for m in req.messages]
    prompt = messages[-1]["content"]

    try:
        normalized_project, normalized_federation, normalized_scope = normalize_scope(
            project_id=req.project_id,
            federation_scope=req.federation_scope,
            knowledge_scope=req.knowledge_scope,
            require_project_id=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        decision = await triage.triage(
            prompt,
            router=request.app.state.router,
            skill_registry=getattr(request.app.state, "skill_registry", None),
            project_id=normalized_project,
            federation_scope=normalized_federation,
            knowledge_scope=normalized_scope,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Triage failed: {exc}") from exc

    return {
        "mode": decision.mode,
        "agents": decision.agents,
        "reason": decision.reason,
        "confidence": decision.confidence,
        "source": decision.source,
    }


@router.get("/agents/{name}/metrics")
async def get_agent_metrics(name: str, request: Request):
    """
    Get metrics for a specific agent.

    Args:
        name: Agent name to retrieve metrics for
        request: FastAPI request object for accessing app state

    Returns:
        Dictionary containing agent usage metrics and statistics

    Raises:
        HTTPException: If agent with the specified name is not found (404)
    """
    try:
        request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
    return request.app.state.registry.agent_metrics(name)


# ---------------------------------------------------------------------------
# Agent Zero — Operator Copilot
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = (
    "api_key=",
    "api-key:",
    "authorization:",
    "bearer ",
    "password=",
    "secret=",
    "token=",
)


def _redact_secrets(text: str) -> str:
    """Strip likely secret values from log/trace text before sending to LLM."""
    import re

    redacted = text
    for pat in _SECRET_PATTERNS:
        redacted = re.sub(
            rf"({re.escape(pat)})(\S+)",
            r"\1[REDACTED]",
            redacted,
            flags=re.IGNORECASE,
        )
    return redacted


class CopilotRequest(BaseModel):
    """Request model for the Agent Zero operator copilot."""

    mode: Literal["logs", "traces", "incident"] = "incident"
    prompt: str = Field(max_length=10_000, description="Operator question or context")
    logs: list[str] = Field(default_factory=list, max_length=50, description="Recent log lines")
    traces: list[dict] = Field(
        default_factory=list, max_length=20, description="Agent trace objects"
    )
    run_id: str | None = Field(default=None, max_length=100)
    service: str | None = Field(default=None, max_length=100)
    severity: Literal["debug", "info", "warning", "error", "critical"] | None = None
    project_id: str | None = Field(default=None, max_length=256)


@router.post("/agents/agent-zero/copilot")
async def agent_zero_copilot(req: CopilotRequest, request: Request):
    """Agent Zero operator copilot — incident analysis and decision support.

    Accepts logs, traces, and operator context. Returns structured analysis
    with facts, hypotheses, and recommended next action. Read-only — never
    executes commands or modifies state.
    """
    try:
        agent = request.app.state.registry.get("agent-zero")
    except KeyError:
        raise HTTPException(status_code=404, detail="agent-zero not registered") from None

    # Build context from logs and traces
    context_parts: list[str] = []

    if req.service:
        context_parts.append(f"Service: {req.service}")
    if req.severity:
        context_parts.append(f"Severity filter: {req.severity}")
    if req.run_id:
        context_parts.append(f"Run ID: {req.run_id}")

    if req.logs:
        redacted_logs = [_redact_secrets(line) for line in req.logs[-30:]]
        context_parts.append("--- Recent logs ---")
        context_parts.extend(redacted_logs)

    if req.traces:
        context_parts.append("--- Agent traces ---")
        import json

        for trace in req.traces[-10:]:
            context_parts.append(_redact_secrets(json.dumps(trace, default=str)))

    # Compose the prompt
    copilot_system = (
        "Tu es en mode Operator Copilot. "
        "Analyse le contexte d'incident ci-dessous. "
        "Structure ta reponse en: "
        "1) FAITS (ce qui s'est passe, preuves dans les logs/traces), "
        "2) HYPOTHESES (causes probables classees par confiance), "
        "3) PROCHAINE ACTION (une seule verification manuelle precise). "
        "Ne propose JAMAIS d'action destructive. "
        "Sois concis et factuel."
    )

    context_block = "\n".join(context_parts) if context_parts else "(aucun contexte fourni)"
    full_prompt = f"{req.prompt}\n\n{context_block}"

    try:
        response = await agent.run(
            full_prompt,
            router=request.app.state.router,
            context=None,
            skill_registry=getattr(request.app.state, "skill_registry", None),
            system_override=copilot_system,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Agent Zero failed: {exc}") from exc

    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
        "operator_context": {
            "mode": req.mode,
            "service": req.service,
            "severity": req.severity,
            "run_id": req.run_id,
            "logs_count": len(req.logs),
            "traces_count": len(req.traces),
        },
    }
