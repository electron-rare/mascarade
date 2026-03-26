"""Health check and system status endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    """Health check endpoint - returns basic system status."""
    health_data = {"status": "healthy"}

    # Add optional metrics if state is initialized
    if hasattr(request.app.state, "router"):
        health_data["providers"] = request.app.state.router.available_providers
    if hasattr(request.app.state, "registry"):
        health_data["agents"] = len(request.app.state.registry)

    return health_data


@router.get("/v1/version")
async def version():
    """Version endpoint - returns API version and service information."""
    return {"version": "v1", "service": "mascarade-core", "api_version": "0.2.0"}


@router.get("/v1/models")
async def list_models(request: Request):
    """OpenAI-compatible model list — used by Xcode Intelligence and other clients.

    Returns the list of available providers and agents as selectable models.
    Format: {"object": "list", "data": [{"id": "...", "object": "model", ...}]}
    """

    models = []
    if hasattr(request.app.state, "router"):
        router_inst = request.app.state.router
        for name in router_inst.available_providers:
            models.append(
                {
                    "id": name,
                    "object": "model",
                    "created": 1700000000,
                    "owned_by": "mascarade",
                }
            )
            # Expose individual models per provider (e.g. ollama:qwen2.5:7b)
            provider = router_inst._providers.get(name)
            if provider:
                try:
                    for model_id in provider.available_models():
                        models.append(
                            {
                                "id": f"{name}:{model_id}",
                                "object": "model",
                                "created": 1700000000,
                                "owned_by": name,
                            }
                        )
                except Exception:
                    pass
    if hasattr(request.app.state, "registry"):
        for agent in request.app.state.registry.list():
            models.append(
                {
                    "id": f"agent:{agent.name}",
                    "object": "model",
                    "created": 1700000000,
                    "owned_by": "mascarade",
                }
            )
    return {"object": "list", "data": models}


@router.get("/health/providers")
async def get_provider_health(request: Request):
    """Provider health metrics endpoint - returns detailed health statistics for all providers."""
    if not hasattr(request.app.state, "router"):
        raise HTTPException(status_code=503, detail="Router not initialized")

    health_monitor = request.app.state.router.health_monitor
    circuit_breaker = request.app.state.router.circuit_breaker
    all_health = health_monitor.get_all_health()

    # Convert ProviderHealth dataclass objects to dictionaries
    providers_health = {}
    for prov_name, prov_health in all_health.items():
        health_dict = asdict(prov_health)
        # Add circuit breaker state
        health_dict["circuit_breaker_state"] = circuit_breaker.get_state(prov_name)
        providers_health[prov_name] = health_dict

    return {
        "providers": providers_health,
        "timestamp": (
            health_monitor.last_check_time.isoformat() if health_monitor.last_check_time else None
        ),
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Prometheus metrics endpoint - exposes metrics in Prometheus format."""
    try:
        from prometheus_client import REGISTRY, generate_latest

        return generate_latest(REGISTRY)
    except ImportError:
        # Prometheus client not available, return empty response
        return "# Prometheus client not installed\n"
