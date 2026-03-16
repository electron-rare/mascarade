"""Authentication and API key management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from mascarade.auth import (
    add_api_key,
    get_active_api_keys,
    remove_api_key,
    require_auth,
)

router = APIRouter(dependencies=[Depends(require_auth)], tags=["auth"])


# --- Models ---


class APIKeyCreate(BaseModel):
    key: str = Field(min_length=1, max_length=256, description="API key to add")


class APIKeyRemove(BaseModel):
    key: str = Field(min_length=1, max_length=256, description="API key to remove")


# --- Endpoints ---


@router.post("/v1/api-keys")
async def create_api_key(req: APIKeyCreate):
    """Add a new API key to the active keys list."""
    add_api_key(req.key)
    return {"status": "ok", "message": "API key added successfully"}


@router.post("/v1/api-keys/remove")
async def delete_api_key(req: APIKeyRemove):
    """Remove an API key from the active keys list."""
    remove_api_key(req.key)
    return {"status": "ok", "message": "API key removed successfully"}


@router.get("/v1/api-keys")
async def list_api_keys():
    """List all active API keys (with partial masking for security)."""
    keys = get_active_api_keys()
    return {"api_keys": [{"key": k[:4] + "***" + k[-4:], "active": True} for k in keys]}
