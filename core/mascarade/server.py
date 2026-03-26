"""Serveur FastAPI — point d'entree HTTP du core Python."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from mascarade.agents import Agent, AgentRegistry
from mascarade.agents.prompt_versioning import PromptHistory, PromptVersion
from mascarade.agents.skills import register_default_skills
from mascarade.auth import (
    add_api_key,
    get_active_api_keys,
    get_current_user,
    hash_api_key,
    remove_api_key,
    require_admin,
    require_auth,
)
from mascarade.cluster import ClusterManager, require_cluster_auth
from mascarade.config import settings
from mascarade.db.connection import close_db_pool, get_db_pool, init_db_pool
from mascarade.db.models import (
    ApiKey,
    ApiKeyCreate,
    ApiKeyCreateResponse,
    User,
    UserCreate,
    UserUpdate,
)
from mascarade.integrations.comfyui import ComfyUIClient
from mascarade.integrations.knowledge_base import (
    knowledge_base_auth_configured,
    knowledge_base_status_detail,
)
from mascarade.integrations.qdrant_client import QdrantClient
from mascarade.integrations.rag_pipeline import RAGPipeline
from mascarade.mcp import McpCallError, McpRuntimeClient, McpServerUnavailable
from mascarade.mcp.client import McpError
from mascarade.observability import AgentTraceBuffer, iso_utc_now, new_run_id
from mascarade.orchestrator import Orchestrator
from mascarade.orchestrator.engine import ExecutionMode
from mascarade.orchestrator.templates import (
    TemplateRegistry,
    register_builtin_templates,
)
from mascarade.provider_admin import (
    PROVIDER_REGISTRY,
    get_providers_status,
    update_provider_keys,
)
from mascarade.device_voice import (
    DevicePlayerEvent,
    DeviceVoiceService,
)
from mascarade.router import Router
from mascarade.router.router import Strategy
from mascarade.usage_tracking import get_all_usage_stats
from mascarade.ollama_compat import mount_ollama_compat

logger = logging.getLogger("mascarade.server")
INDUSTRIAL_MCP_SERVER_KEYS = {"cockpit-ops", "plm", "qms", "mes", "erp", "wms", "dcs"}


def hash_api_key(key: str) -> str:
    """Hash API key for author tracking (returns first 8 chars of SHA-256)."""
    if not key:
        return ""
    return hashlib.sha256(key.encode()).hexdigest()[:8]


@asynccontextmanager
async def lifespan(app: FastAPI):
    router = Router()
    registry = AgentRegistry()
    register_default_skills(registry)
    trace_buffer = AgentTraceBuffer()
    cluster = ClusterManager(
        router=router,
        agents_count_provider=lambda: len(registry),
    )
    orchestrator = Orchestrator(
        router=router,
        registry=registry,
        trace_buffer=trace_buffer,
        cluster=cluster,
    )
    template_registry = TemplateRegistry()
    register_builtin_templates(template_registry)

    app.state.router = router
    app.state.registry = registry
    app.state.orchestrator = orchestrator
    app.state.trace_buffer = trace_buffer
    app.state.cluster = cluster
    app.state.template_registry = template_registry
    app.state.mcp = McpRuntimeClient(trace_buffer=trace_buffer)
    app.state.comfyui = ComfyUIClient() if settings.comfyui_url else None
    app.state.device_voice = DeviceVoiceService(router=router)
    _qdrant = QdrantClient() if settings.qdrant_url else None
    app.state.qdrant = _qdrant
    app.state.rag = RAGPipeline(qdrant=_qdrant) if _qdrant else None

    registry.load()

    # Initialize database pool if DATABASE_URL is configured
    if settings.database_url:
        try:
            await init_db_pool()
            logger.info("Database pool initialized")
        except Exception as e:
            logger.warning("Failed to initialize database pool: %s", e)

    # Start P2P node if enabled
    # Start P2P node (auto-selects backend)
    await cluster.start_p2p()

    # Start health checks for all registered providers
    router.health_monitor.start_health_checks(list(router._providers.values()))

    yield

    # Stop health checks
    await router.health_monitor.stop_health_checks()

    # Stop P2P node
    await cluster.stop_p2p()

    # Clean up benchmark trigger
    if hasattr(app.state, "benchmark_trigger"):
        await app.state.benchmark_trigger.close()

    await cluster.close()
    if app.state.comfyui is not None:
        await app.state.comfyui.close()

    # Close database pool
    if settings.database_url:
        await close_db_pool()
        logger.info("Database pool closed")
    if app.state.qdrant is not None:
        await app.state.qdrant.close()
    if app.state.rag is not None:
        await app.state.rag.close()


app = FastAPI(title="Mascarade Core", version="0.1.0", lifespan=lifespan)


# --- Models ---


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=100_000)


RoutingPolicy = Literal["auto", "strong", "cheap", "fast"]


class SendRequest(BaseModel):
    messages: list[Message] = Field(max_length=200)
    strategy: Strategy = Strategy.BEST
    routing_policy: RoutingPolicy = "auto"
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=100)
    system: str | None = Field(default=None, max_length=10_000)
    response_format: dict | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=1000)
    system_prompt: str = Field(max_length=50_000)
    preferred_provider: str | None = Field(default=None, max_length=50)
    preferred_model: str | None = Field(default=None, max_length=100)
    preferred_role: str | None = Field(default=None, max_length=100)
    strategy: Strategy = Strategy.ROUTELLM
    routing_policy: RoutingPolicy = "auto"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)


class AgentUpdate(BaseModel):
    description: str = Field(max_length=1000)
    system_prompt: str = Field(max_length=50_000)
    preferred_provider: str | None = Field(default=None, max_length=50)
    preferred_model: str | None = Field(default=None, max_length=100)
    preferred_role: str | None = Field(default=None, max_length=100)
    strategy: Strategy = Strategy.ROUTELLM
    routing_policy: RoutingPolicy = "auto"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)
    version_note: str | None = Field(default=None, max_length=500)


class PromptVersionResponse(BaseModel):
    version_number: int = Field(ge=1)
    timestamp: str = Field(min_length=1, max_length=100)
    content: str = Field(max_length=500_000)
    author_hash: str = Field(max_length=64)
    diff: str | None = None
    note: str | None = Field(default=None, max_length=1000)


class PromptHistoryResponse(BaseModel):
    versions: list[PromptVersionResponse]
    total: int = Field(ge=0)


class AgentRoutingOverride(BaseModel):
    preferred_role: str | None = Field(default=None, max_length=100)
    preferred_provider: str | None = Field(default=None, max_length=50)
    preferred_model: str | None = Field(default=None, max_length=100)
    routing_policy: RoutingPolicy | None = None


class TaskRequest(BaseModel):
    agent_names: list[str] = Field(max_length=20)
    prompt: str = Field(min_length=1, max_length=100_000)
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    routing_overrides: dict[str, AgentRoutingOverride] = Field(default_factory=dict)


class TemplateDeployRequest(BaseModel):
    input: str = Field(min_length=1, max_length=100_000)
    routing_overrides: dict[str, AgentRoutingOverride] = Field(default_factory=dict)


class ClusterForwardSendRequest(SendRequest):
    peer_id: str | None = Field(default=None, max_length=100)
    preferred_role: str | None = Field(default=None, max_length=100)
    allow_local: bool = True


class KnowledgeBaseAppendRequest(BaseModel):
    content: str = Field(min_length=1, max_length=50_000)


class KnowledgeBaseCreateRequest(BaseModel):
    parent_id: str = Field(max_length=200)
    title: str = Field(max_length=500)
    content: str = Field(default="", max_length=50_000)


class KnowledgeScribeRequest(BaseModel):
    messages: list[Message] = Field(max_length=200)
    push_to: str | None = Field(default=None, max_length=200)
    run_id: str | None = Field(default=None, max_length=64)


class GitHubDispatchRequest(BaseModel):
    workflow_file: str = Field(min_length=1, max_length=200)
    ref: str | None = Field(default=None, max_length=200)
    inputs: dict[str, str | int | float | bool] = Field(default_factory=dict)
    run_id: str | None = Field(default=None, max_length=64)


class GitHubDispatchStatusRequest(BaseModel):
    dispatch_id: str = Field(min_length=1, max_length=200)
    run_id: str | None = Field(default=None, max_length=64)


class IndustrialMcpToolRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = Field(default=None, max_length=64)


class FreeCADCreateDocumentRequest(BaseModel):
    output_path: str = Field(min_length=1, max_length=400)
    name: str = Field(default="McpDocument", min_length=1, max_length=80)
    primitive: Literal["box"] = "box"
    length: float = Field(default=10.0, gt=0, le=10_000)
    width: float = Field(default=8.0, gt=0, le=10_000)
    height: float = Field(default=6.0, gt=0, le=10_000)
    run_id: str | None = Field(default=None, max_length=64)


class FreeCADExportDocumentRequest(BaseModel):
    document_path: str = Field(min_length=1, max_length=400)
    output_path: str = Field(min_length=1, max_length=400)
    run_id: str | None = Field(default=None, max_length=64)


class FreeCADRunScriptRequest(BaseModel):
    script: str = Field(min_length=1, max_length=20_000)
    output_path: str | None = Field(default=None, max_length=400)
    run_id: str | None = Field(default=None, max_length=64)


class OpenSCADValidateRequest(BaseModel):
    source: str = Field(min_length=1, max_length=20_000)
    run_id: str | None = Field(default=None, max_length=64)


class OpenSCADRenderRequest(BaseModel):
    source: str = Field(min_length=1, max_length=20_000)
    output_path: str = Field(min_length=1, max_length=400)
    run_id: str | None = Field(default=None, max_length=64)


class ComfyUIGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    negative_prompt: str = Field(default="", max_length=10_000)
    checkpoint: str | None = Field(default=None, max_length=200)
    width: int = Field(default=512, ge=64, le=2048)
    height: int = Field(default=512, ge=64, le=2048)
    steps: int = Field(default=20, ge=1, le=150)
    cfg: float = Field(default=7.0, ge=1.0, le=30.0)
    seed: int = -1


class ComfyUIWorkflowRequest(BaseModel):
    workflow: dict


class RateLimitUpdate(BaseModel):
    """Request model for updating user rate limits."""

    requests_per_minute: int | None = Field(default=None, ge=0)
    requests_per_hour: int | None = Field(default=None, ge=0)
    requests_per_day: int | None = Field(default=None, ge=0)
    tokens_per_day: int | None = Field(default=None, ge=0)
class QdrantCreateCollectionRequest(BaseModel):
    vector_size: int = Field(gt=0, le=65536)
    distance: Literal["Cosine", "Euclid", "Dot"] = "Cosine"
    on_disk_payload: bool = False


class QdrantUpsertPointsRequest(BaseModel):
    points: list[dict[str, Any]] = Field(max_length=1000)
    wait: bool = True


class QdrantSearchRequest(BaseModel):
    query_vector: list[float] = Field(max_length=65536)
    limit: int = Field(default=10, gt=0, le=100)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    with_payload: bool = True
    with_vector: bool = False
    filter_conditions: dict[str, Any] | None = None


class QdrantRecommendRequest(BaseModel):
    positive: list[str | int] = Field(min_length=1, max_length=100)
    negative: list[str | int] | None = Field(default=None, max_length=100)
    limit: int = Field(default=10, gt=0, le=100)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    with_payload: bool = True
    with_vector: bool = False
    filter_conditions: dict[str, Any] | None = None


class QdrantSemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    limit: int = Field(default=10, gt=0, le=100)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class QdrantRAGRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    collection: str = Field(default="mascarade-kb", min_length=1, max_length=100)
    retrieve_k: int = Field(default=20, gt=0, le=100)
    rerank_top_k: int = Field(default=5, gt=0, le=20)
    model: str | None = None
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)


class RAGIngestRequest(BaseModel):
    collection: str = Field(default="mascarade-kb", min_length=1, max_length=100)
    texts: list[str] = Field(min_length=1, max_length=100)
    payloads: list[dict[str, Any]] | None = None
    chunk_size: int = Field(default=800, gt=100, le=4000)
    chunk_overlap: int = Field(default=100, ge=0, le=500)


class RAGSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    collection: str = Field(default="mascarade-kb", min_length=1, max_length=100)
    limit: int = Field(default=10, gt=0, le=50)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class BenchmarkRunRequest(BaseModel):
    domain: str | None = Field(default=None, max_length=50)
    providers: list[str] | None = Field(default=None, max_length=10)
    difficulty: str | None = Field(default=None, max_length=20)
    limit: int | None = Field(default=None, gt=0, le=100)


class ModelDeploymentWebhook(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100)
    event_type: str = Field(default="deployment", max_length=50)
    domain: str | None = Field(default=None, max_length=50)
    limit: int | None = Field(default=None, gt=0, le=100)
    background: bool = Field(default=True)
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Route publique ---


@app.get("/health")
async def health():
    """Health check endpoint - returns basic system status."""
    health_data = {"status": "ok"}

    # Add optional metrics if state is initialized
    if hasattr(app.state, "router"):
        health_data["providers"] = app.state.router.available_providers
    if hasattr(app.state, "registry"):
        health_data["agents"] = len(app.state.registry)

    return health_data


@app.get("/v1/version")
async def version():
    """Version endpoint - returns API version and service information."""
    return {
        "version": "v1",
        "service": "mascarade-core",
        "api_version": "0.1.0"
    }
@app.post("/v1/chat/completions", response_model_exclude_unset=True)
@app.get("/health/providers")
async def get_provider_health():
    """Provider health metrics endpoint - returns detailed health statistics for all providers."""
    if not hasattr(app.state, "router"):
        raise HTTPException(status_code=503, detail="Router not initialized")

    health_monitor = app.state.router.health_monitor
    circuit_breaker = app.state.router.circuit_breaker
    all_health = health_monitor.get_all_health()

    # Convert ProviderHealth dataclass objects to dictionaries
    health_data = {}
    for provider_name, provider_health in all_health.items():
        circuit_state = circuit_breaker.get_state(provider_name)
        health_data[provider_name] = {
            "provider_name": provider_health.provider_name,
            "health_score": provider_health.health_score,
            "circuit_state": circuit_state.value,
            "latency_p50": provider_health.latency_p50,
            "latency_p95": provider_health.latency_p95,
            "latency_p99": provider_health.latency_p99,
            "error_rate": provider_health.error_rate,
            "availability": provider_health.availability,
            "total_requests": provider_health.total_requests,
        }

    return health_data


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint."""
    # Determine model and provider
    model_str = req.model if req.model else settings.default_model
    provider = None
    model = model_str

    # Parse model string for provider prefix (e.g., "apple-coreml:model")
    if ":" in model_str:
        parts = model_str.split(":", 1)
        provider_prefix = parts[0]
        model = parts[1]

        # Get supported provider names (these are the known provider types)
        supported_providers = [
            "apple-coreml",
            "ollama",
            "mlx",
            "openai",
            "claude",
            "anthropic",
            "mistral",
            "bedrock",
            "gemini",
        ]

        # Validate provider prefix
        if provider_prefix not in supported_providers:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported model prefix '{provider_prefix}'.",
            )

        provider = provider_prefix

        # Check if provider is available
        if provider not in app.state.router.available_providers:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": f"Provider '{provider}' is not configured or unavailable.",
                    "providers": app.state.router.available_providers,
                },
            )
    else:
        # Use default provider if no prefix
        provider = settings.default_provider
        model = model_str or settings.default_model

    # Convert messages to router format
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    # Handle streaming if requested
    if req.stream:
        async def stream_response():
            """Generate SSE stream of chat completion chunks."""
            chat_id = f"chatcmpl-{new_run_id()}"
            created = int(time.time())

            # Send initial chunk with role
            initial_chunk = ChatCompletionChunk(
                id=chat_id,
                object="chat.completion.chunk",
                created=created,
                model=model_str,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(role="assistant"),
                        finish_reason=None,
                    )
                ],
            )
            yield f"data: {initial_chunk.model_dump_json()}\n\n"

            # Stream tokens
            try:
                async for token in app.state.router.stream(
                    messages,
                    strategy=Strategy.SPECIFIC,
                    provider=provider,
                    model=model,
                    system=None,
                    temperature=req.temperature,
                    max_tokens=req.max_tokens or 4096,
                ):
                    chunk = ChatCompletionChunk(
                        id=chat_id,
                        object="chat.completion.chunk",
                        created=created,
                        model=model_str,
                        choices=[
                            ChatCompletionChunkChoice(
                                index=0,
                                delta=ChatCompletionChunkDelta(content=token),
                                finish_reason=None,
                            )
                        ],
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"

                # Send final chunk with finish_reason
                final_chunk = ChatCompletionChunk(
                    id=chat_id,
                    object="chat.completion.chunk",
                    created=created,
                    model=model_str,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta=ChatCompletionChunkDelta(),
                            finish_reason="stop",
                        )
                    ],
                )
                yield f"data: {final_chunk.model_dump_json()}\n\n"

            except ValueError as exc:
                logger.warning("Chat completions streaming failed: %s", exc)
                # For streaming errors, we can't raise HTTPException
                # Send an error in SSE format
                error_data = {"error": {"message": str(exc), "type": "invalid_request_error"}}
                yield f"data: {json.dumps(error_data)}\n\n"

            # Send [DONE] marker
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming response (original implementation)
    try:
        response = await app.state.router.send(
            messages,
            strategy=Strategy.SPECIFIC,
            provider=provider,
            model=model,
            system=None,
            response_format=None,
            temperature=req.temperature,
            max_tokens=req.max_tokens or 4096,
        )
    except ValueError as exc:
        logger.warning("Chat completions request rejected: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Build OpenAI-compatible response
    chat_id = f"chatcmpl-{new_run_id()}"
    created = int(time.time())

    # Extract usage info
    usage_dict = response.usage or {}
    prompt_tokens = usage_dict.get("input_tokens", 0)
    completion_tokens = usage_dict.get("output_tokens", 0)
    total_tokens = usage_dict.get("total_tokens", prompt_tokens + completion_tokens)

    usage = ChatCompletionUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )

    choice = ChatCompletionChoice(
        index=0,
        message=ChatCompletionMessage(
            role="assistant",
            content=response.content,
        ),
        finish_reason="stop",
    )

    return ChatCompletionResponse(
        id=chat_id,
        object="chat.completion",
        created=created,
        model=model_str,
        choices=[choice],
        usage=usage,
    )


# --- Routes protegees ---

protected = APIRouter(prefix="/v1", dependencies=[Depends(require_auth)])
cluster_protected = APIRouter(
    prefix="/v1/cluster/node",
    dependencies=[Depends(require_cluster_auth)],
)


def _serialize_agent(agent: Agent) -> dict[str, object]:
    return {
        "name": agent.name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "preferred_provider": agent.preferred_provider,
        "preferred_model": agent.preferred_model,
        "preferred_role": agent.preferred_role,
        "strategy": agent.strategy.value,
        "routing_policy": agent.routing_policy,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "builtin": app.state.registry.is_builtin(agent.name),
    }


def _mcp_http_exception(error: McpError) -> HTTPException:
    detail = error.structured_content.get("error") if error.structured_content else None
    code = ""
    if isinstance(detail, dict):
        code = str(detail.get("code") or "").strip()
    if not code:
        code = str(error.error_code or "").strip()

    if code == "invalid_arguments":
        status = 400
    elif code == "missing_secret":
        status = 503
    elif isinstance(error, McpServerUnavailable):
        status = 503
    else:
        status = 502

    return HTTPException(status_code=status, detail=str(error))


# --- Gestion des cles API ---


class ProviderKeyUpdate(BaseModel):
    keys: dict[str, str] = Field(description="Map ENV_VAR -> value")


class APIKeyCreate(BaseModel):
    key: str = Field(min_length=8, max_length=256, description="Nouvelle cle API")


class APIKeyRemove(BaseModel):
    key: str = Field(min_length=1, max_length=256, description="Cle API a retirer")


@protected.post("/api-keys")
async def create_api_key(req: APIKeyCreate):
    add_api_key(req.key)
    return {"status": "ok", "message": "API key added successfully"}


@protected.post("/api-keys/remove")
async def delete_api_key(req: APIKeyRemove):
    remove_api_key(req.key)
    return {"status": "ok", "message": "API key removed successfully"}


@protected.get("/api-keys")
async def list_api_keys():
    keys = get_active_api_keys()
    return {"api_keys": [{"key": k[:4] + "***" + k[-4:], "active": True} for k in keys]}


@protected.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role_id": current_user.role_id,
        "is_active": current_user.is_active,
        "rate_limits": current_user.rate_limits,
    }


# --- User Management ---


@protected.get("/users")
async def list_users(_: None = Depends(require_admin)):
    """List all users (admin only)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, username, email, role_id, is_active, created_at, updated_at
                FROM users
                ORDER BY created_at DESC
                """
            )
            users = [User.from_record(dict(row)) for row in rows]
            return {"users": [user.model_dump() for user in users]}
    except Exception as e:
        logger.error("Error listing users: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error listing users")


@protected.post("/users")
async def create_user(req: UserCreate, _: None = Depends(require_admin)):
    """Create a new user (admin only)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        async with pool.acquire() as conn:
            # Check if username already exists
            existing = await conn.fetchrow(
                "SELECT id FROM users WHERE username = $1",
                req.username,
            )
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Username '{req.username}' already exists",
                )

            # Check if email already exists
            existing_email = await conn.fetchrow(
                "SELECT id FROM users WHERE email = $1",
                req.email,
            )
            if existing_email:
                raise HTTPException(
                    status_code=400,
                    detail=f"Email '{req.email}' already exists",
                )

            # Verify role exists
            role = await conn.fetchrow(
                "SELECT id FROM roles WHERE id = $1",
                req.role_id,
            )
            if not role:
                raise HTTPException(
                    status_code=400,
                    detail=f"Role ID {req.role_id} does not exist",
                )

            # Create user
            row = await conn.fetchrow(
                """
                INSERT INTO users (username, email, role_id, is_active)
                VALUES ($1, $2, $3, $4)
                RETURNING id, username, email, role_id, is_active, created_at, updated_at
                """,
                req.username,
                req.email,
                req.role_id,
                req.is_active,
            )

            user = User.from_record(dict(row))
            logger.info("User created: id=%d, username=%s", user.id, user.username)
            return user.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating user: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error creating user")


@protected.get("/users/{user_id}")
async def get_user(user_id: int, _: None = Depends(require_admin)):
    """Get a user by ID (admin only)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, username, email, role_id, is_active, created_at, updated_at
                FROM users
                WHERE id = $1
                """,
                user_id,
            )

            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"User with ID {user_id} not found",
                )

            user = User.from_record(dict(row))
            return user.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting user: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error getting user")


@protected.put("/users/{user_id}")
async def update_user(
    user_id: int,
    req: UserUpdate,
    _: None = Depends(require_admin),
):
    """Update a user (admin only)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        async with pool.acquire() as conn:
            # Check if user exists
            existing = await conn.fetchrow(
                "SELECT id FROM users WHERE id = $1",
                user_id,
            )
            if not existing:
                raise HTTPException(
                    status_code=404,
                    detail=f"User with ID {user_id} not found",
                )

            # Build update query dynamically based on provided fields
            updates = []
            params = []
            param_count = 1

            if req.username is not None:
                # Check if new username is taken
                username_check = await conn.fetchrow(
                    "SELECT id FROM users WHERE username = $1 AND id != $2",
                    req.username,
                    user_id,
                )
                if username_check:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Username '{req.username}' already exists",
                    )
                updates.append(f"username = ${param_count}")
                params.append(req.username)
                param_count += 1

            if req.email is not None:
                # Check if new email is taken
                email_check = await conn.fetchrow(
                    "SELECT id FROM users WHERE email = $1 AND id != $2",
                    req.email,
                    user_id,
                )
                if email_check:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Email '{req.email}' already exists",
                    )
                updates.append(f"email = ${param_count}")
                params.append(req.email)
                param_count += 1

            if req.role_id is not None:
                # Verify role exists
                role = await conn.fetchrow(
                    "SELECT id FROM roles WHERE id = $1",
                    req.role_id,
                )
                if not role:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Role ID {req.role_id} does not exist",
                    )
                updates.append(f"role_id = ${param_count}")
                params.append(req.role_id)
                param_count += 1

            if req.is_active is not None:
                updates.append(f"is_active = ${param_count}")
                params.append(req.is_active)
                param_count += 1

            if not updates:
                raise HTTPException(
                    status_code=400,
                    detail="No fields to update",
                )

            # Always update updated_at
            updates.append(f"updated_at = NOW()")
            params.append(user_id)

            query = f"""
                UPDATE users
                SET {', '.join(updates)}
                WHERE id = ${param_count}
                RETURNING id, username, email, role_id, is_active, created_at, updated_at
            """

            row = await conn.fetchrow(query, *params)
            user = User.from_record(dict(row))
            logger.info("User updated: id=%d, username=%s", user.id, user.username)
            return user.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating user: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating user")


@protected.delete("/users/{user_id}")
async def delete_user(user_id: int, _: None = Depends(require_admin)):
    """Delete a user (admin only)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        async with pool.acquire() as conn:
            # Check if user exists
            existing = await conn.fetchrow(
                "SELECT id FROM users WHERE id = $1",
                user_id,
            )
            if not existing:
                raise HTTPException(
                    status_code=404,
                    detail=f"User with ID {user_id} not found",
                )

            # Delete the user (cascading deletes will handle api_keys)
            await conn.execute(
                "DELETE FROM users WHERE id = $1",
                user_id,
            )

            logger.info("User deleted: id=%d", user_id)
            return {"status": "ok", "message": f"User {user_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting user: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error deleting user")


@protected.put("/users/{user_id}/rate-limit")
async def update_user_rate_limit(
    user_id: int,
    req: RateLimitUpdate,
    _: None = Depends(require_admin),
):
    """Update rate limit for a user (admin only)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        async with pool.acquire() as conn:
            # Check if user exists
            existing = await conn.fetchrow(
                "SELECT id, username FROM users WHERE id = $1",
                user_id,
            )
            if not existing:
                raise HTTPException(
                    status_code=404,
                    detail=f"User with ID {user_id} not found",
                )

            # Build rate limits JSON
            rate_limits = {
                "requests_per_minute": req.requests_per_minute,
                "requests_per_hour": req.requests_per_hour,
                "requests_per_day": req.requests_per_day,
                "tokens_per_day": req.tokens_per_day,
            }

            # Update user's rate limits
            await conn.execute(
                """
                UPDATE users
                SET rate_limits = $1::jsonb, updated_at = NOW()
                WHERE id = $2
                """,
                json.dumps(rate_limits),
                user_id,
            )

            logger.info(
                "Rate limits updated for user: id=%d, username=%s",
                user_id,
                existing["username"],
            )
            return {
                "status": "ok",
                "message": f"Rate limits updated for user {user_id}",
                "rate_limits": rate_limits,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating rate limits: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating rate limits")


# --- API Key Management ---


@protected.post("/users/{user_id}/api-keys", status_code=201)
async def create_user_api_key(
    user_id: int,
    req: ApiKeyCreate,
    _: None = Depends(require_admin),
):
    """Create a new API key for a user (admin only)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        async with pool.acquire() as conn:
            # Check if user exists
            user_row = await conn.fetchrow(
                "SELECT id FROM users WHERE id = $1",
                user_id,
            )
            if not user_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"User with ID {user_id} not found",
                )

            # Generate a secure random API key (32 bytes = 64 hex chars)
            api_key = secrets.token_hex(32)
            key_hash = hash_api_key(api_key)
            key_prefix = api_key[:8]

            # Insert the API key into the database
            row = await conn.fetchrow(
                """
                INSERT INTO api_keys (user_id, key_hash, key_prefix, name, is_active, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, user_id, key_hash, key_prefix, name, is_active, created_at, expires_at, last_used_at
                """,
                user_id,
                key_hash,
                key_prefix,
                req.name,
                True,  # is_active
                req.expires_at,
            )

            api_key_obj = ApiKey.from_record(dict(row))
            logger.info(
                "API key created: id=%d, user_id=%d, name=%s",
                api_key_obj.id,
                user_id,
                req.name,
            )

            # Return the API key object with the actual key (shown only once)
            return ApiKeyCreateResponse(
                api_key=api_key_obj,
                key=api_key,
            ).model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating API key: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error creating API key")


@protected.get("/users/{user_id}/api-keys")
async def list_user_api_keys(
    user_id: int,
    _: None = Depends(require_admin),
):
    """List all API keys for a user (admin only)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        async with pool.acquire() as conn:
            # Check if user exists
            user_row = await conn.fetchrow(
                "SELECT id FROM users WHERE id = $1",
                user_id,
            )
            if not user_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"User with ID {user_id} not found",
                )

            # Fetch all API keys for the user
            rows = await conn.fetch(
                """
                SELECT id, user_id, key_hash, key_prefix, name, is_active, created_at, expires_at, last_used_at
                FROM api_keys
                WHERE user_id = $1
                ORDER BY created_at DESC
                """,
                user_id,
            )

            api_keys = [ApiKey.from_record(dict(row)) for row in rows]
            return {"api_keys": [key.model_dump() for key in api_keys]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing API keys: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error listing API keys")


@protected.delete("/users/{user_id}/api-keys/{key_id}")
async def revoke_user_api_key(
    user_id: int,
    key_id: int,
    _: None = Depends(require_admin),
):
    """Revoke (delete) an API key for a user (admin only)."""
    pool = get_db_pool()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    try:
        async with pool.acquire() as conn:
            # Check if API key exists and belongs to the user
            key_row = await conn.fetchrow(
                """
                SELECT id, user_id, name
                FROM api_keys
                WHERE id = $1 AND user_id = $2
                """,
                key_id,
                user_id,
            )

            if not key_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"API key with ID {key_id} not found for user {user_id}",
                )

            # Delete the API key
            await conn.execute(
                "DELETE FROM api_keys WHERE id = $1",
                key_id,
            )

            logger.info(
                "API key revoked: id=%d, user_id=%d, name=%s",
                key_id,
                user_id,
                key_row["name"],
            )
            return {
                "status": "ok",
                "message": f"API key {key_id} revoked successfully",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error revoking API key: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error revoking API key")


# --- Usage Statistics ---


@protected.get("/admin/usage/stats")
async def get_usage_statistics(
    start_date: datetime | None = Query(default=None, description="Start date for filtering (ISO format)"),
    end_date: datetime | None = Query(default=None, description="End date for filtering (ISO format)"),
    _: None = Depends(require_admin),
):
    """Get aggregated usage statistics for all users (admin only)."""
    try:
        stats = await get_all_usage_stats(start_date=start_date, end_date=end_date)
        return {"stats": [stat.model_dump() for stat in stats]}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Error fetching usage statistics: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching usage statistics")


# --- LLM ---


@protected.post("/send")
async def send(req: SendRequest):
    messages = [m.model_dump() for m in req.messages]
    try:
        response = await app.state.router.send(
            messages,
            strategy=req.strategy,
            routing_policy=req.routing_policy,
            provider=req.provider,
            model=req.model,
            system=req.system,
            response_format=req.response_format,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except ValueError as exc:
        logger.warning("Send request rejected: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid request parameters") from exc
    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


@protected.get("/providers")
async def list_providers():
    return {"providers": app.state.router.available_providers}


@protected.get("/providers/status")
async def providers_status():
    return {"providers": get_providers_status(app.state.router)}


@protected.put("/providers/{name}/key")
async def update_provider(name: str, req: ProviderKeyUpdate):
    if name not in PROVIDER_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")
    result = update_provider_keys(
        name,
        req.keys,
        app.state.router,
        persist_env=False,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@protected.get("/providers/bedrock/models")
async def bedrock_models():
    """List Bedrock models including fine-tuned custom models."""
    provider = app.state.router._providers.get("bedrock")
    if not provider:
        raise HTTPException(status_code=503, detail="Bedrock provider not configured")
    return {
        "default": provider.default_model,
        "available": provider.available_models(),
        "custom": provider.custom_models(),
    }


@protected.get("/providers/bedrock/finetune-jobs")
async def bedrock_finetune_jobs():
    """Check status of Bedrock fine-tuning jobs."""
    provider = app.state.router._providers.get("bedrock")
    if not provider:
        raise HTTPException(status_code=503, detail="Bedrock provider not configured")
    jobs = await provider.finetune_jobs()
    return {"jobs": jobs}


# --- Metrics ---


@protected.get("/router/metrics")
async def metrics_summary():
    return await app.state.router.metrics_summary()


@protected.get("/router/metrics/{provider}")
async def metrics_provider(provider: str):
    stats = app.state.router.provider_metrics(provider)
    if not stats:
        raise HTTPException(status_code=404, detail="Provider has no metrics yet")
    return stats


@protected.post("/router/metrics/reset")
async def metrics_reset():
    await app.state.router.reset_metrics()
    return {"status": "ok"}


# --- Prometheus scrape endpoint (public) ---


@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics for scraping."""
    try:
        from prometheus_client import REGISTRY, generate_latest
        from prometheus_client import CONTENT_TYPE_LATEST
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        raise HTTPException(status_code=501, detail="prometheus_client not installed")


@protected.get("/device/v1/voice/replies/{reply_id}.wav")
async def device_voice_reply_audio(reply_id: str, request: Request):
    from fastapi.responses import Response as _Response

    service: DeviceVoiceService = request.app.state.device_voice
    audio = service.get_reply_audio(reply_id)
    if audio is None:
        raise HTTPException(status_code=404, detail="Reply audio not found or expired")
    return _Response(content=audio.payload, media_type=audio.content_type)


# --- RAG routes (KXKM compute: nomic-embed-text + qwen3:4b rerank + devstral) ---

def _require_rag(request: Request) -> "RAGPipeline":
    rag = request.app.state.rag
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not available (QDRANT_URL not set)")
    return rag


@protected.post("/rag/ingest", status_code=202)
async def rag_ingest(req: RAGIngestRequest, request: Request):
    """Ingère des textes dans Qdrant avec embeddings nomic-embed-text (768d)."""
    rag = _require_rag(request)
    n = await rag.ingest(
        req.collection, req.texts, req.payloads, req.chunk_size, req.chunk_overlap
    )
    return {"collection": req.collection, "points_inserted": n}


@protected.post("/rag/search")
async def rag_search(req: RAGSearchRequest, request: Request):
    """Recherche sémantique dans Qdrant (embed via nomic-embed-text)."""
    rag = _require_rag(request)
    results = await rag.search(req.collection, req.query, req.limit, req.score_threshold)
    return {"query": req.query, "collection": req.collection, "results": results}


@protected.post("/rag/query")
async def rag_query(req: QdrantRAGRequest, request: Request):
    """Pipeline RAG complet : embed → Qdrant → rerank (qwen3:4b) → synthèse (devstral)."""
    rag = _require_rag(request)
    result = await rag.query(
        req.collection,
        req.query,
        retrieve_k=req.retrieve_k,
        rerank_top_k=req.rerank_top_k,
        model=req.model,
        temperature=req.temperature,
    )
    return result


# Mapping agent → collection Qdrant pour enrichissement RAG automatique
_AGENT_RAG_COLLECTIONS: dict[str, str] = {
    "firmware-engineer": "kb-firmware",
    "kicad-designer": "kb-kicad",
    "spice-expert": "kb-spice",
    "freecad-designer": "kb-freecad",
    "components-expert": "kb-components",
    "openseeker": "kb-firmware",  # fallback; fan-out handled by OpenSeekerAgent itself
}
_RAG_RETRIEVE_K = 12
_RAG_RERANK_TOP_K = 4


async def _rag_enrich(messages: list[dict], agent_name: str, rag) -> list[dict]:
    """Injecte du contexte RAG dans le dernier message utilisateur si une collection existe."""
    collection = _AGENT_RAG_COLLECTIONS.get(agent_name)
    if not collection or rag is None:
        return messages

    # Extraire la query du dernier message user
    query = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"), None
    )
    if not query:
        return messages

    try:
        # Search → rerank
        chunks = await rag.search(collection, query, limit=_RAG_RETRIEVE_K, score_threshold=0.4)
        if not chunks:
            return messages
        ranked = await rag._reranker.rerank(query, chunks, top_k=_RAG_RERANK_TOP_K)
        top = [c for c in ranked if c.get("score", 0) >= 1]
        # Fallback : si reranker donne tous 0, utiliser les top chunks Qdrant bruts
        if not top:
            top = chunks[:_RAG_RERANK_TOP_K]
        context = "\n\n---\n\n".join(c["text"] for c in top)
        if not context:
            return messages
    except Exception as e:
        logger.debug("RAG enrich failed for %s: %s", agent_name, e)
        return messages

    # Injecter le contexte dans une copie des messages
    enriched = list(messages)
    last_user_idx = next(
        (i for i, m in reversed(list(enumerate(enriched))) if m.get("role") == "user"),
        None,
    )
    if last_user_idx is not None:
        enriched[last_user_idx] = {
            **enriched[last_user_idx],
            "content": (
                f"## Knowledge base context\n\n{context}\n\n---\n\n"
                f"{enriched[last_user_idx]['content']}"
            ),
        }
    return enriched


class AgentRunRequest(BaseModel):
    messages: list[dict[str, str]]
    rag: bool = True  # Activer l'enrichissement RAG automatique (défaut: True)


@protected.post("/agents/{name}/run")
async def run_agent(name: str, req: AgentRunRequest, request: Request):
    """Exécute un agent par nom. Enrichit automatiquement avec RAG si une collection existe."""
    try:
        agent = request.app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    messages = req.messages
    rag_used = False
    if req.rag and request.app.state.rag and name in _AGENT_RAG_COLLECTIONS:
        messages = await _rag_enrich(messages, name, request.app.state.rag)
        rag_used = messages is not req.messages

    try:
        response = await agent.run_with_history(
            messages, router=request.app.state.router
        )
    except Exception as exc:
        logger.warning("Agent run failed for %s: %s", name, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
        "rag_collection": _AGENT_RAG_COLLECTIONS.get(name) if rag_used else None,
    }


class OpenSeekerRequest(BaseModel):
    query: str
    collections: list[str] | None = None  # None = all collections
    retrieve_k: int = 6
    rerank_top_k: int = 8
    score_threshold: float = 0.40


@protected.post("/agents/openseeker/search")
async def openseeker_search(req: OpenSeekerRequest, request: Request):
    """Multi-hop RAG search: fan-out across collections, rerank, synthesize."""
    from mascarade.agents.openseeker_agent import OpenSeekerAgent

    try:
        agent = request.app.state.registry.get("openseeker")
    except KeyError:
        agent = OpenSeekerAgent()

    rag = request.app.state.rag
    router = request.app.state.router

    try:
        result = await agent.cross_domain_query(
            req.query,
            router=router,
            rag=rag,
            collections=req.collections,
            retrieve_k=req.retrieve_k,
            rerank_top_k=req.rerank_top_k,
            score_threshold=req.score_threshold,
        )
    except Exception as exc:
        logger.warning("OpenSeeker search failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return result


_KILL_LIFE_ROOT = Path(os.getenv("KILL_LIFE_ROOT", "/home/clems/Kill_LIFE")).resolve()
_CLI_AGENT_TIMEOUT_S = int(os.getenv("CLI_AGENT_TIMEOUT_S", "60"))


class CliAgentRunRequest(BaseModel):
    agent: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int | None = None


@protected.post("/cli-agents/run")
async def run_cli_agent(req: CliAgentRunRequest):
    """Run a Kill_LIFE CLI agent script from KILL_LIFE_ROOT/tools/."""
    # Resolve and validate path stays within tools/
    try:
        script = (_KILL_LIFE_ROOT / "tools" / req.agent).resolve()
        script.relative_to(_KILL_LIFE_ROOT / "tools")
    except (ValueError, Exception):
        raise HTTPException(status_code=400, detail=f"Invalid agent path: {req.agent!r}")

    if not script.exists():
        raise HTTPException(status_code=404, detail=f"CLI agent not found: {req.agent!r}")

    timeout_s = (req.timeout_ms / 1000) if req.timeout_ms else _CLI_AGENT_TIMEOUT_S
    env = {**dict(os.environ), "KILL_LIFE_ROOT": str(_KILL_LIFE_ROOT), **req.env}

    # Use bash for shell scripts to avoid execute permission issues
    cmd = ["bash", str(script)] if script.suffix == ".sh" else [str(script)]

    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            *req.args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(_KILL_LIFE_ROOT),
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise HTTPException(status_code=504, detail=f"CLI agent timed out after {timeout_s}s")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("CLI agent launch failed for %s: %s", req.agent, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    duration_ms = int((time.monotonic() - t0) * 1000)
    return {
        "ok": proc.returncode == 0,
        "agent": req.agent,
        "exit_code": proc.returncode,
        "output": stdout_b.decode("utf-8", errors="replace"),
        "stderr": stderr_b.decode("utf-8", errors="replace"),
        "duration_ms": duration_ms,
    }


app.include_router(protected)
app.include_router(cluster_protected)

# Mount Ollama-compatible API
mount_ollama_compat(app)


def start():
    import uvicorn

    uvicorn.run(app, host=settings.core_host, port=settings.core_port)


if __name__ == "__main__":
    start()
