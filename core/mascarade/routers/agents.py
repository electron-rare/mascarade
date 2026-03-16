"""Agent management endpoints."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.agents import Agent
from mascarade.agents.prompt_versioning import PromptHistory, PromptVersion
from mascarade.auth import require_auth
from mascarade.router.router import Strategy

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)], tags=["agents"])


# --- Models ---


RoutingPolicy = Literal["auto", "strong", "cheap", "fast"]


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=100_000)


class AgentCreate(BaseModel):
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
    messages: list[Message] = Field(max_length=200)
    strategy: Strategy = Strategy.BEST
    routing_policy: RoutingPolicy = "auto"
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=100)
    system: str | None = Field(default=None, max_length=10_000)
    response_format: dict | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)


# --- Helper functions ---


def hash_api_key(key: str) -> str:
    """Hash API key for author tracking (returns first 8 chars of SHA-256)."""
    if not key:
        return ""
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def _serialize_agent(agent: Agent, request: Request) -> dict[str, object]:
    """Serialize an agent to a dictionary."""
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
    """Create a new agent."""
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


@router.get("/agents")
async def list_agents(request: Request):
    """List all registered agents."""
    return {
        "agents": [
            _serialize_agent(agent, request)
            for agent in request.app.state.registry.list()
        ]
    }


@router.get("/agents/{name}")
async def get_agent(name: str, request: Request):
    """Get a specific agent by name."""
    try:
        agent = request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{name}' not found"
        ) from None
    return _serialize_agent(agent, request)


@router.put("/agents/{name}")
async def update_agent(name: str, req: AgentUpdate, request: Request):
    """Update an existing agent."""
    try:
        agent = request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{name}' not found"
        ) from None
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
        prompt_history._versions = [
            PromptVersion(**v) for v in agent.prompt_versions
        ]

        # Add new version
        new_version = prompt_history.add_version(
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
    """Delete an agent."""
    try:
        agent = request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{name}' not found"
        ) from None
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
    """Run an agent with the given messages."""
    if not req.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    try:
        agent = request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{name}' not found"
        ) from None

    messages = [m.model_dump() for m in req.messages]
    prompt = messages[-1]["content"]
    context = messages[:-1] if len(messages) > 1 else None
    response = await agent.run(prompt, router=request.app.state.router, context=context)
    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


@router.get("/agents/{name}/metrics")
async def get_agent_metrics(name: str, request: Request):
    """Get metrics for a specific agent."""
    try:
        agent = request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{name}' not found"
        ) from None
    return request.app.state.registry.agent_metrics(name)
