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

router = APIRouter(prefix="/v1/api", dependencies=[Depends(require_auth)], tags=["providers"])


# --- Models ---


class ProviderKeyUpdate(BaseModel):
    """Request model for updating provider API keys."""

    keys: dict[str, str] = Field(description="Map ENV_VAR -> value")


# --- Endpoints ---


@router.get("/providers")
async def list_providers(request: Request):
    """
    List all available LLM providers in the system.

    Args:
        request: FastAPI request object for accessing app state

    Returns:
        Dictionary with "providers" key containing list of provider names
    """
    return {"providers": request.app.state.router.available_providers}


@router.get("/providers/status")
async def providers_status(request: Request):
    """
    Get status and configuration details for all providers.

    Args:
        request: FastAPI request object for accessing app state

    Returns:
        Dictionary with "providers" key containing detailed status for each provider
        including API key configuration, model availability, and health status
    """
    return {"providers": get_providers_status(request.app.state.router)}


@router.put("/providers/{name}/key")
async def update_provider(name: str, req: ProviderKeyUpdate, request: Request):
    """
    Update API keys for a specific provider.

    Args:
        name: Provider name (e.g., "openai", "anthropic", "bedrock")
        req: Dictionary mapping environment variable names to their values
        request: FastAPI request object for accessing app state

    Returns:
        Dictionary containing update status and provider information

    Raises:
        HTTPException: If provider name is not recognized (404)
    """
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
    """
    List AWS Bedrock models including fine-tuned custom models.

    Args:
        request: FastAPI request object for accessing app state

    Returns:
        Dictionary containing "models" (base models) and "custom_models" (fine-tuned)

    Raises:
        HTTPException: If Bedrock provider is not initialized or available (404)
    """
    provider = request.app.state.router._providers.get("bedrock")
    if not provider:
        raise HTTPException(status_code=404, detail="Bedrock provider not available")
    return {
        "models": provider.list_models(),
        "custom_models": provider.list_custom_models(),
    }


@router.get("/providers/bedrock/finetune-jobs")
async def bedrock_finetune_jobs(request: Request):
    """
    Check status of AWS Bedrock fine-tuning jobs.

    Args:
        request: FastAPI request object for accessing app state

    Returns:
        List of fine-tuning job statuses with job details and progress

    Raises:
        HTTPException: If Bedrock provider is not initialized or available (404)
    """
    provider = request.app.state.router._providers.get("bedrock")
    if not provider:
        raise HTTPException(status_code=404, detail="Bedrock provider not available")
    return provider.list_finetune_jobs()
