"""Mistral AI Studio agents — discovery and execution endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.auth import require_auth

logger = logging.getLogger("mascarade.routers.mistral_agents")

router = APIRouter(
    prefix="/v1/api/mistral-agents",
    dependencies=[Depends(require_auth)],
    tags=["mistral-agents"],
)


class MistralAgentRunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    conversation_id: str | None = Field(default=None, max_length=200)


@router.get("/discover")
async def discover_agents():
    """Discover agents from Mistral AI Studio workspace."""
    from mascarade.agents.mistral_agents import discover_mistral_agents

    agents = await discover_mistral_agents()
    return {"agents": agents, "count": len(agents)}


@router.get("/status")
async def mistral_agents_status(request: Request):
    """List registered Mistral remote agents."""
    from mascarade.agents.mistral_agents import MistralRemoteAgent

    registry = request.app.state.registry
    mistral_agents = [
        {
            "name": agent.name,
            "description": agent.description,
            "agent_id": agent.agent_id,
            "has_conversation": agent.conversation_id is not None,
        }
        for agent in registry.list()
        if isinstance(agent, MistralRemoteAgent)
    ]
    return {"agents": mistral_agents, "count": len(mistral_agents)}


@router.post("/{agent_name}/run")
async def run_mistral_agent(
    agent_name: str, req: MistralAgentRunRequest, request: Request
):
    """Run a Mistral AI Studio agent."""
    from mascarade.agents.mistral_agents import MistralRemoteAgent

    try:
        agent = request.app.state.registry.get(agent_name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        ) from None

    if not isinstance(agent, MistralRemoteAgent):
        raise HTTPException(
            status_code=400,
            detail=f"Agent '{agent_name}' is not a Mistral remote agent",
        )

    if not agent.agent_id:
        raise HTTPException(
            status_code=503,
            detail=f"Agent '{agent_name}' has no agent_id configured. "
            "Set it via /api/mistral-agents/configure or in the agent config.",
        )

    # Set conversation_id if continuing
    if req.conversation_id:
        agent.conversation_id = req.conversation_id

    try:
        response = await agent.run(req.prompt)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "agent": agent_name,
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
        "conversation_id": agent.conversation_id,
    }


@router.post("/{agent_name}/configure")
async def configure_mistral_agent(
    agent_name: str, request: Request, agent_id: str = ""
):
    """Configure the Mistral agent_id for a registered agent."""
    from mascarade.agents.mistral_agents import MistralRemoteAgent

    try:
        agent = request.app.state.registry.get(agent_name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        ) from None

    if not isinstance(agent, MistralRemoteAgent):
        raise HTTPException(
            status_code=400,
            detail=f"Agent '{agent_name}' is not a Mistral remote agent",
        )

    agent.agent_id = agent_id
    return {"status": "ok", "agent": agent_name, "agent_id": agent_id}


@router.post("/{agent_name}/reset")
async def reset_conversation(agent_name: str, request: Request):
    """Reset the conversation state for a Mistral agent."""
    from mascarade.agents.mistral_agents import MistralRemoteAgent

    try:
        agent = request.app.state.registry.get(agent_name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        ) from None

    if isinstance(agent, MistralRemoteAgent):
        agent.reset_conversation()

    return {"status": "ok", "agent": agent_name, "conversation_id": None}
