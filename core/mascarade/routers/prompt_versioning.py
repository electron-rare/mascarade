"""Prompt versioning endpoints for agent prompt history and rollback."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

from mascarade.agents.prompt_versioning import PromptHistory, PromptVersion

router = APIRouter(tags=["agents"])


@router.get("/agents/{name}/prompts/history")
async def get_prompt_history(name: str, request: Request):
    """Get the prompt version history for an agent.

    Args:
        name: Agent name
        request: FastAPI request object

    Returns:
        Dictionary with "versions" key containing list of version dicts
    """
    try:
        agent = request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{name}' not found"
        ) from None

    return {"versions": agent.prompt_versions}


@router.post("/agents/{name}/prompts/rollback/{version}")
async def rollback_prompt(name: str, version: int, request: Request):
    """Rollback an agent's prompt to a specific version.

    Args:
        name: Agent name
        version: Version number to rollback to
        request: FastAPI request object

    Returns:
        Dictionary with rollback result including the current prompt
    """
    try:
        agent = request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{name}' not found"
        ) from None

    if version < 1:
        raise HTTPException(
            status_code=400, detail=f"Invalid version: {version}"
        )

    # Find the version to rollback to
    target_version = None
    for v in agent.prompt_versions:
        if v["version_number"] == version:
            target_version = v
            break

    if target_version is None:
        raise HTTPException(
            status_code=400, detail=f"Invalid version: {version}"
        )

    # Store old prompt before rollback
    old_prompt = agent.system_prompt
    new_prompt = target_version["content"]

    # Rollback the prompt
    agent.system_prompt = new_prompt

    # Create a new version entry for the rollback
    from mascarade.agents.prompt_versioning import iso_utc_now

    version_number = len(agent.prompt_versions) + 1
    rollback_entry = {
        "version_number": version_number,
        "timestamp": iso_utc_now(),
        "content": old_prompt,
        "author_hash": "system",
        "diff": None,
        "note": f"Rollback to version {version}",
    }
    agent.prompt_versions.append(rollback_entry)

    # Save the registry
    request.app.state.registry.save()

    return {
        "message": f"Rolled back to version {version}",
        "current_prompt": agent.system_prompt,
    }
