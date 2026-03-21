"""Knowledge base routes for search and content management."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.auth import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])


def knowledge_base_auth_configured() -> bool:
    """Check if knowledge base authentication is configured."""
    from mascarade.config import settings
    return bool(getattr(settings, "knowledge_base_provider", ""))


def _check_kb_auth() -> bool:
    """Check KB auth using the function from mascarade.server (supports monkeypatching)."""
    import mascarade.server as server_mod
    fn = getattr(server_mod, "knowledge_base_auth_configured", knowledge_base_auth_configured)
    return fn()


@router.get("/knowledge-base/search")
async def knowledge_base_search(q: str, request: Request):
    """Search the knowledge base via MCP client."""
    if not _check_kb_auth():
        raise HTTPException(status_code=503, detail="Knowledge base not configured")

    mcp = getattr(request.app.state, "mcp", None)
    if mcp is None:
        raise HTTPException(status_code=503, detail="MCP client not available")

    result = await mcp.knowledge_base_search(q)
    return result


class RunAndPushRequest(BaseModel):
    messages: list[dict] = Field(default_factory=list)
    push_to: str | None = None
    run_id: str | None = None


@router.post("/agents/{agent_name}/run-and-push")
async def run_and_push(agent_name: str, req: RunAndPushRequest, request: Request):
    """Run an agent and push the result to the knowledge base."""
    if not _check_kb_auth():
        raise HTTPException(status_code=503, detail="Knowledge base not configured")

    mcp = getattr(request.app.state, "mcp", None)
    if mcp is None:
        raise HTTPException(status_code=503, detail="MCP client not available")

    run_id = req.run_id or f"run-{secrets.token_hex(8)}"

    # Get the agent and run it
    try:
        agent = request.app.state.registry.get(agent_name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        ) from None

    # Run the agent
    prompt = req.messages[-1]["content"] if req.messages else ""
    response = await agent.run(prompt, router=request.app.state.router)

    # Push to knowledge base
    pushed = False
    if req.push_to:
        await mcp.knowledge_base_append(
            req.push_to,
            response.content,
            run_id=run_id,
        )
        pushed = True

    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
        "pushed_to_knowledge_base": pushed,
        "run_id": run_id,
    }
