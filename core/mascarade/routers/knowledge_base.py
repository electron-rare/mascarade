"""Knowledge base routes for search and content management."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.auth import require_auth
from mascarade.project_scope import normalize_scope

router = APIRouter(dependencies=[Depends(require_auth)])


def knowledge_base_auth_configured() -> bool:
    """Check if knowledge base authentication is configured."""
    from mascarade.config import settings

    return bool(getattr(settings, "knowledge_base_provider", ""))


def _check_kb_auth() -> bool:
    """Check KB auth using the function from mascarade.server (supports monkeypatching)."""
    import mascarade.server as server_mod

    fn = getattr(
        server_mod, "knowledge_base_auth_configured", knowledge_base_auth_configured
    )
    return fn()


def _parse_federation_scope(raw_scope: str | None) -> list[str] | None:
    if not raw_scope:
        return None
    values = [item.strip() for item in raw_scope.split(",") if item.strip()]
    return values or None


@router.get("/knowledge-base/search")
async def knowledge_base_search(
    q: str,
    request: Request,
    project_id: str,
    limit: int = 10,
    federation_scope: str | None = None,
    knowledge_scope: str = "project",
):
    """Search the knowledge base via MCP client."""
    if not _check_kb_auth():
        raise HTTPException(status_code=503, detail="Knowledge base not configured")

    mcp = getattr(request.app.state, "mcp", None)
    if mcp is None:
        raise HTTPException(status_code=503, detail="MCP client not available")

    try:
        normalized_project, normalized_federation, normalized_scope = normalize_scope(
            project_id=project_id,
            federation_scope=_parse_federation_scope(federation_scope),
            knowledge_scope=knowledge_scope,
            require_project_id=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await mcp.knowledge_base_search(
        q,
        limit=max(1, min(limit, 50)),
        project_id=normalized_project,
        federation_scope=normalized_federation,
        knowledge_scope=normalized_scope,
    )
    return result


class RunAndPushRequest(BaseModel):
    messages: list[dict] = Field(default_factory=list)
    push_to: str | None = None
    run_id: str | None = None
    project_id: str | None = Field(default=None, max_length=256)
    federation_scope: list[str] | None = None
    knowledge_scope: str = "project"


@router.post("/agents/{agent_name}/run-and-push")
async def run_and_push(agent_name: str, req: RunAndPushRequest, request: Request):
    """Run an agent and push the result to the knowledge base."""
    if not _check_kb_auth():
        raise HTTPException(status_code=503, detail="Knowledge base not configured")

    mcp = getattr(request.app.state, "mcp", None)
    if mcp is None:
        raise HTTPException(status_code=503, detail="MCP client not available")

    run_id = req.run_id or f"run-{secrets.token_hex(8)}"
    try:
        normalized_project, normalized_federation, normalized_scope = normalize_scope(
            project_id=req.project_id,
            federation_scope=req.federation_scope,
            knowledge_scope=req.knowledge_scope,
            require_project_id=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Get the agent and run it
    try:
        agent = request.app.state.registry.get(agent_name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        ) from None

    # Run the agent
    prompt = req.messages[-1]["content"] if req.messages else ""
    response = await agent.run(
        prompt,
        router=request.app.state.router,
        context=req.messages[:-1] if len(req.messages) > 1 else None,
        project_id=normalized_project,
        federation_scope=normalized_federation,
        knowledge_scope=normalized_scope,
    )

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
