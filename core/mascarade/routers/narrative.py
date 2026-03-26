"""Narrative MCP routes for ai-novel-engine pipeline.

Exposes character tracking, plot management, consistency checking,
and world state queries via the Book Series + Writer MCP servers.

Opt-in: only active when NARRATIVE_MCP_ENABLED=true.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.auth import require_auth
from mascarade.mcp.narrative import NarrativeMcpClient

router = APIRouter(
    prefix="/v1/narrative",
    tags=["narrative"],
    dependencies=[Depends(require_auth)],
)


def _get_narrative(request: Request) -> NarrativeMcpClient:
    client: NarrativeMcpClient | None = getattr(request.app.state, "narrative_mcp", None)
    if client is None or not client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Narrative MCP integration not configured (set NARRATIVE_MCP_ENABLED=true)",
        )
    return client


# ------------------------------------------------------------------
# POST /v1/narrative/characters
# ------------------------------------------------------------------


class CharacterRequest(BaseModel):
    name: str = Field(..., description="Character name")
    attributes: dict | None = Field(default=None, description="Character attributes")
    book_id: str | None = Field(default=None, description="Book identifier")
    knowledge_aspect: str | None = Field(
        default=None,
        description="If set, query character knowledge for this aspect instead of tracking",
    )


class CharacterResponse(BaseModel):
    ok: bool = True
    character: str
    data: dict = Field(default_factory=dict)


@router.post("/characters", response_model=CharacterResponse)
async def track_or_query_character(req: CharacterRequest, request: Request):
    """Track/update a character, or query character knowledge.

    When `knowledge_aspect` is provided, queries the Writer MCP server
    for the character's knowledge base. Otherwise, creates or updates
    the character in the Book Series tracker.
    """
    client = _get_narrative(request)

    try:
        if req.knowledge_aspect:
            data = await client.get_character_knowledge(req.name, aspect=req.knowledge_aspect)
        else:
            data = await client.track_character(
                req.name, attributes=req.attributes, book_id=req.book_id
            )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return CharacterResponse(character=req.name, data=data)


# ------------------------------------------------------------------
# POST /v1/narrative/consistency
# ------------------------------------------------------------------


class ConsistencyRequest(BaseModel):
    text: str = Field(..., description="Narrative text to check")
    book_id: str | None = Field(default=None, description="Book identifier")
    scope: str = Field(
        default="all",
        description="Check scope: all, characters, plot, timeline",
    )


class ConsistencyResponse(BaseModel):
    ok: bool
    issues: list[dict] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)


@router.post("/consistency", response_model=ConsistencyResponse)
async def check_consistency(req: ConsistencyRequest, request: Request):
    """Check narrative consistency against tracked world state and character knowledge."""
    client = _get_narrative(request)

    try:
        result = await client.check_consistency(req.text, book_id=req.book_id, scope=req.scope)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ConsistencyResponse(
        ok=result.get("ok", True),
        issues=result.get("issues", []),
        details={k: v for k, v in result.items() if k not in ("ok", "issues")},
    )


# ------------------------------------------------------------------
# GET /v1/narrative/world
# ------------------------------------------------------------------


class WorldStateResponse(BaseModel):
    ok: bool = True
    book_id: str = "default"
    world: dict = Field(default_factory=dict)


@router.get("/world", response_model=WorldStateResponse)
async def get_world_state(book_id: str | None = None, request: Request = None):
    """Retrieve the full world state from the Book Series tracker."""
    client = _get_narrative(request)

    try:
        data = await client.get_world_state(book_id=book_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return WorldStateResponse(
        book_id=book_id or "default",
        world=data,
    )
