"""Provider admin endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.auth import require_auth
from mascarade.provider_admin import (
    PROVIDER_REGISTRY,
    get_providers_status,
    update_provider_keys,
)

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)], tags=["providers"])


# --- Models ---


class ProviderKeyUpdate(BaseModel):
    keys: dict[str, str] = Field(description="Map ENV_VAR -> value")


# --- Endpoints ---


@router.get("/providers")
async def list_providers(request: Request):
    """List all available providers."""
    return {"providers": request.app.state.router.available_providers}


@router.get("/providers/status")
async def providers_status(request: Request):
    """Get status of all providers including configuration."""
    return {"providers": get_providers_status(request.app.state.router)}


@router.put("/providers/{name}/key")
async def update_provider(name: str, req: ProviderKeyUpdate, request: Request):
    """Update API keys for a specific provider."""
    if name not in PROVIDER_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")
    result = update_provider_keys(
        name,
        req.keys,
        request.app.state.router,
        persist_env=False,
    )
    return result


@router.get("/providers/bedrock/models")
async def bedrock_models(request: Request):
    """List Bedrock models including fine-tuned custom models."""
    provider = request.app.state.router._providers.get("bedrock")
    if not provider:
        raise HTTPException(status_code=404, detail="Bedrock provider not available")
    return {
        "models": provider.list_models(),
        "custom_models": provider.list_custom_models(),
    }


@router.get("/providers/bedrock/finetune-jobs")
async def bedrock_finetune_jobs(request: Request):
    """Check status of Bedrock fine-tuning jobs."""
    provider = request.app.state.router._providers.get("bedrock")
    if not provider:
        raise HTTPException(status_code=404, detail="Bedrock provider not available")
    return provider.list_finetune_jobs()
