"""Skill management endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.agents.skill import Skill
from mascarade.auth import require_auth

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)], tags=["skills"])


# --- Models ---


class SkillCreate(BaseModel):
    """Request model for creating a new skill."""

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=1000)
    category: str = Field(min_length=1, max_length=50)
    instruction: str = Field(max_length=50_000)
    tools: list[str] = Field(default_factory=list)
    examples: list[dict] = Field(default_factory=list)
    enabled: bool = True
    version: int = 1


class SkillUpdate(BaseModel):
    """Request model for updating an existing skill."""

    description: str = Field(max_length=1000)
    category: str = Field(min_length=1, max_length=50)
    instruction: str = Field(max_length=50_000)
    tools: list[str] = Field(default_factory=list)
    examples: list[dict] = Field(default_factory=list)
    enabled: bool = True
    version: int = 1


# --- Helpers ---


def _serialize_skill(skill: Skill, request: Request) -> dict[str, object]:
    """Serialize a skill to a dictionary for API response."""
    data = asdict(skill)
    data["builtin"] = request.app.state.skill_registry.is_builtin(skill.name)
    return data


# --- Endpoints ---


@router.post("/skills")
async def create_skill(req: SkillCreate, request: Request):
    """Create a new skill."""
    if req.name in request.app.state.skill_registry:
        raise HTTPException(
            status_code=409, detail=f"Skill '{req.name}' already exists"
        )
    skill = Skill(
        name=req.name,
        description=req.description,
        category=req.category,
        instruction=req.instruction,
        tools=req.tools,
        examples=req.examples,
        enabled=req.enabled,
        version=req.version,
    )
    request.app.state.skill_registry.register(skill)
    request.app.state.skill_registry.save()
    return _serialize_skill(skill, request)


@router.get("/skills")
async def list_skills(request: Request):
    """List all registered skills."""
    return {
        "skills": [
            _serialize_skill(skill, request)
            for skill in request.app.state.skill_registry.list()
        ]
    }


@router.get("/skills/{name}")
async def get_skill(name: str, request: Request):
    """Get a specific skill by name."""
    try:
        skill = request.app.state.skill_registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Skill '{name}' not found"
        ) from None
    return _serialize_skill(skill, request)


@router.put("/skills/{name}")
async def update_skill(name: str, req: SkillUpdate, request: Request):
    """Update an existing skill (builtin skills are read-only)."""
    try:
        skill = request.app.state.skill_registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Skill '{name}' not found"
        ) from None
    if request.app.state.skill_registry.is_builtin(name):
        raise HTTPException(
            status_code=403,
            detail="Built-in skills are read-only.",
        )

    skill.description = req.description
    skill.category = req.category
    skill.instruction = req.instruction
    skill.tools = req.tools
    skill.examples = req.examples
    skill.enabled = req.enabled
    skill.version = req.version

    request.app.state.skill_registry.save()
    return _serialize_skill(skill, request)


@router.delete("/skills/{name}")
async def delete_skill(name: str, request: Request):
    """Delete a skill (builtin skills cannot be deleted)."""
    try:
        request.app.state.skill_registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Skill '{name}' not found"
        ) from None
    if request.app.state.skill_registry.is_builtin(name):
        raise HTTPException(
            status_code=403,
            detail="Built-in skills are read-only and cannot be deleted.",
        )

    # Remove skill from all agents that have it assigned
    for agent in request.app.state.registry.list():
        if hasattr(agent, "skills") and name in agent.skills:
            agent.skills.remove(name)
    request.app.state.registry.save()

    request.app.state.skill_registry.remove(name)
    request.app.state.skill_registry.save()
    return {"message": f"Skill '{name}' deleted successfully"}


@router.post("/skills/{name}/assign/{agent_name}")
async def assign_skill(name: str, agent_name: str, request: Request):
    """Assign a skill to an agent."""
    try:
        request.app.state.skill_registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Skill '{name}' not found"
        ) from None
    try:
        agent = request.app.state.registry.get(agent_name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        ) from None

    if not hasattr(agent, "skills"):
        agent.skills = []
    if name in agent.skills:
        raise HTTPException(
            status_code=409,
            detail=f"Skill '{name}' already assigned to agent '{agent_name}'",
        )

    agent.skills.append(name)
    request.app.state.registry.save()
    return {"message": f"Skill '{name}' assigned to agent '{agent_name}'"}


@router.delete("/skills/{name}/assign/{agent_name}")
async def unassign_skill(name: str, agent_name: str, request: Request):
    """Remove a skill from an agent."""
    try:
        request.app.state.skill_registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Skill '{name}' not found"
        ) from None
    try:
        agent = request.app.state.registry.get(agent_name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        ) from None

    if not hasattr(agent, "skills") or name not in agent.skills:
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{name}' not assigned to agent '{agent_name}'",
        )

    agent.skills.remove(name)
    request.app.state.registry.save()
    return {"message": f"Skill '{name}' removed from agent '{agent_name}'"}


@router.get("/agents/{agent_name}/skills")
async def list_agent_skills(agent_name: str, request: Request):
    """List all skills assigned to an agent."""
    try:
        agent = request.app.state.registry.get(agent_name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        ) from None

    skill_names = getattr(agent, "skills", [])
    skills = []
    for sname in skill_names:
        try:
            skill = request.app.state.skill_registry.get(sname)
            skills.append(_serialize_skill(skill, request))
        except KeyError:
            pass  # skill was removed but still referenced — skip

    return {"skills": skills}
