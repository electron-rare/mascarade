"""Serveur FastAPI — point d'entree HTTP du core Python."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
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
from mascarade.routers.health import router as health_router
from mascarade.usage_tracking import get_all_usage_stats

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
    limit: int = Field(default=5, gt=0, le=20)
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


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
async def prometheus_metrics():
    """Expose Prometheus metrics for scraping — no auth required."""
    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        from starlette.responses import Response

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="prometheus_client is not installed",
        )


# --- Cache ---


@protected.get("/cache/stats")
async def cache_stats():
    return app.state.router.cache.get_stats()


@protected.post("/cache/reset")
async def cache_reset():
    app.state.router.cache.clear()
    return {"status": "ok"}


# --- Load Balancer ---


@protected.get("/load-balancer/stats")
async def lb_stats():
    return app.state.router.load_balancer.get_load_stats()


@protected.post("/load-balancer/reset")
async def lb_reset():
    app.state.router.load_balancer.reset_stats()
    return {"status": "ok"}


# --- Fallback ---


@protected.get("/fallback/stats")
async def fallback_stats():
    return app.state.router.fallback.get_failure_stats()


@protected.post("/fallback/reset")
async def fallback_reset():
    app.state.router.fallback.reset()
    return {"status": "ok"}


# --- Agents ---


@protected.post("/agents")
async def create_agent(req: AgentCreate):
    agent = Agent(
        name=req.name,
        description=req.description,
        system_prompt=req.system_prompt,
        preferred_provider=req.preferred_provider,
        preferred_model=req.preferred_model,
        preferred_role=req.preferred_role,
        strategy=req.strategy,
        routing_policy=req.routing_policy,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    app.state.registry.register(agent)
    app.state.registry.save()
    return _serialize_agent(agent)


@protected.get("/agents")
async def list_agents():
    return {"agents": [_serialize_agent(agent) for agent in app.state.registry.list()]}


@protected.get("/agents/{name}")
async def get_agent(name: str):
    try:
        agent = app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
    return _serialize_agent(agent)


@protected.put("/agents/{name}")
async def update_agent(name: str, req: AgentUpdate, request: Request):
    try:
        agent = app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
    if app.state.registry.is_builtin(name):
        raise HTTPException(
            status_code=403,
            detail="Built-in agents are read-only; create a dynamic agent from the UI to edit routing.",
        )

    # Check if system_prompt is changing
    old_system_prompt = agent.system_prompt
    system_prompt_changed = old_system_prompt != req.system_prompt

    # Update agent fields
    agent.description = req.description
    agent.system_prompt = req.system_prompt
    agent.preferred_provider = req.preferred_provider
    agent.preferred_model = req.preferred_model
    agent.preferred_role = req.preferred_role
    agent.strategy = req.strategy
    agent.routing_policy = req.routing_policy
    agent.temperature = req.temperature
    agent.max_tokens = req.max_tokens

    # Create version if system_prompt changed
    if system_prompt_changed:
        # Get API key from request headers for author tracking
        auth_header = request.headers.get("Authorization", "")
        api_key = ""
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        author_hash = hash_api_key(api_key)

        # Create PromptHistory and load existing versions
        prompt_history = PromptHistory(storage_path=None)
        prompt_history._versions = [
            PromptVersion(**v) for v in agent.prompt_versions
        ]

        # Add new version
        new_version = prompt_history.add_version(
            content=req.system_prompt,
            author_hash=author_hash,
            note=req.version_note,
        )

        # Update agent's prompt_versions
        agent.prompt_versions = [asdict(v) for v in prompt_history._versions]

    app.state.registry.save()
    return _serialize_agent(agent)


@protected.delete("/agents/{name}")
async def delete_agent(name: str):
    try:
        agent = app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
    if app.state.registry.is_builtin(name):
        raise HTTPException(
            status_code=403,
            detail="Built-in agents are read-only and cannot be deleted.",
        )

    app.state.registry.remove(name)
    app.state.registry.save()
    return {"message": f"Agent '{name}' deleted successfully"}


@protected.post("/agents/{name}/run")
async def run_agent(name: str, req: SendRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="At least one message is required")

    try:
        agent = app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None

    messages = [m.model_dump() for m in req.messages]
    prompt = messages[-1]["content"]
    context = messages[:-1] if len(messages) > 1 else None
    response = await agent.run(prompt, router=app.state.router, context=context)
    return {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


@protected.get("/agents/{name}/metrics")
async def get_agent_metrics(name: str):
    try:
        agent = app.state.registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
    return app.state.registry.agent_metrics(name)


# --- Orchestration ---


@protected.post("/orchestrate")
async def orchestrate(req: TaskRequest):
    try:
        run = await app.state.orchestrator.run(
            req.agent_names,
            req.prompt,
            mode=req.mode,
            routing_overrides={
                agent_name: override.model_dump()
                for agent_name, override in req.routing_overrides.items()
            },
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent not found: {exc}") from exc
    return {
        "run_id": run.run_id,
        "mode": run.mode.value,
        "results": [
            {
                "agent": r.agent_name,
                "step": r.step,
                "content": r.response.content,
                "model": r.response.model,
                "provider": r.response.provider,
                "remote": r.remote,
                "selected_by": r.selected_by,
                "peer_id": r.peer_id,
                "node_id": r.node_id,
                "role": r.role,
                **({"error": r.error} if r.error else {}),
            }
            for r in run.results
        ],
    }


@protected.get("/orchestrate/templates")
async def list_templates():
    """List all available workflow templates."""
    templates = app.state.template_registry.list()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "agent_names": t.agent_names,
            "mode": t.mode.value,
            "documentation": t.documentation,
            "builtin": app.state.template_registry.is_builtin(t.id),
        }
        for t in templates
    ]


@protected.get("/orchestrate/templates/{template_id}")
async def get_template(template_id: str):
    """Get a specific workflow template by ID."""
    try:
        template = app.state.template_registry.get(template_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Template not found: {template_id}"
        ) from exc
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "agent_names": template.agent_names,
        "mode": template.mode.value,
        "routing_overrides": template.routing_overrides,
        "documentation": template.documentation,
        "builtin": app.state.template_registry.is_builtin(template.id),
    }


@protected.post("/orchestrate/templates/{template_id}/deploy")
async def deploy_template(template_id: str, req: TemplateDeployRequest):
    """Deploy a workflow template with user input."""
    try:
        template = app.state.template_registry.get(template_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Template not found: {template_id}"
        ) from exc

    # Merge template routing_overrides with request overrides (request takes precedence)
    routing_overrides = {}
    if template.routing_overrides:
        routing_overrides.update(template.routing_overrides)
    if req.routing_overrides:
        routing_overrides.update(
            {
                agent_name: override.model_dump()
                for agent_name, override in req.routing_overrides.items()
            }
        )

    try:
        run = await app.state.orchestrator.run(
            template.agent_names,
            req.input,
            mode=template.mode,
            routing_overrides=routing_overrides,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent not found: {exc}") from exc

    return {
        "run_id": run.run_id,
        "template_id": template_id,
        "mode": run.mode.value,
        "results": [
            {
                "agent": r.agent_name,
                "step": r.step,
                "content": r.response.content,
                "model": r.response.model,
                "provider": r.response.provider,
                "remote": r.remote,
                "selected_by": r.selected_by,
                "peer_id": r.peer_id,
                "node_id": r.node_id,
                "role": r.role,
                **({"error": r.error} if r.error else {}),
            }
            for r in run.results
        ],
    }


# --- Cluster / multi-node ---


@protected.get("/cluster/identity")
async def cluster_identity():
    return app.state.cluster.local_identity().to_dict()


@protected.get("/cluster/peers")
async def cluster_peers():
    peers = await app.state.cluster.probe_peers()
    return {
        "node": app.state.cluster.local_identity().to_dict(),
        "peers": [peer.to_dict() for peer in peers],
    }


@protected.post("/cluster/forward/send")
async def cluster_forward_send(req: ClusterForwardSendRequest):
    payload = req.model_dump(exclude={"peer_id", "preferred_role", "allow_local"})
    return await app.state.cluster.forward_send(
        peer_id=req.peer_id,
        preferred_role=req.preferred_role,
        allow_local=req.allow_local,
        payload=payload,
    )


@cluster_protected.get("/identity")
async def cluster_node_identity():
    return app.state.cluster.local_identity().to_dict()


@cluster_protected.post("/send")
async def cluster_node_send(req: SendRequest):
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
        logger.warning("Cluster send request rejected: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid request parameters") from exc

    return {
        "node_id": settings.node_id,
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
    }


# --- Analytics ---


class ProviderCostSummary(BaseModel):
    provider: str
    model: str
    total_cost: float = Field(ge=0.0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    request_count: int = Field(ge=0)


class CostAnalyticsResponse(BaseModel):
    total_cost: float = Field(ge=0.0)
    total_requests: int = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    by_provider: list[ProviderCostSummary]


@protected.get("/v1/analytics/cost")
async def get_cost_analytics(
    limit: int = Query(default=1000, ge=1, le=5000),
    run_id: str | None = Query(default=None, max_length=64),
):
    """
    Get cost analytics aggregated from trace events.

    Args:
        limit: Maximum number of events to analyze (default: 1000)
        run_id: Optional run ID to filter by

    Returns:
        Cost analytics with totals and breakdowns by provider/model
    """
    from mascarade.analytics import get_cost_calculator

    # Get recent trace events with token usage
    events = app.state.trace_buffer.recent(
        limit=limit,
        run_id=run_id,
    )

    # Filter events that have token usage
    events_with_usage = [e for e in events if e.token_usage]

    # Aggregate by (provider, model)
    aggregates: dict[tuple[str, str], dict] = {}
    cost_calc = get_cost_calculator()

    for event in events_with_usage:
        if not event.provider or not event.model:
            continue

        key = (event.provider, event.model)
        if key not in aggregates:
            aggregates[key] = {
                "provider": event.provider,
                "model": event.model,
                "total_cost": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "request_count": 0,
            }

        input_tokens = event.token_usage.get("input_tokens", 0) or event.token_usage.get("prompt_tokens", 0)
        output_tokens = event.token_usage.get("output_tokens", 0) or event.token_usage.get("completion_tokens", 0)

        # Calculate cost for this event
        cost = cost_calc.calculate_cost(
            provider=event.provider,
            model=event.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        aggregates[key]["total_cost"] += cost
        aggregates[key]["input_tokens"] += input_tokens
        aggregates[key]["output_tokens"] += output_tokens
        aggregates[key]["request_count"] += 1

    # Calculate totals
    total_cost = sum(agg["total_cost"] for agg in aggregates.values())
    total_requests = sum(agg["request_count"] for agg in aggregates.values())
    total_input_tokens = sum(agg["input_tokens"] for agg in aggregates.values())
    total_output_tokens = sum(agg["output_tokens"] for agg in aggregates.values())

    # Convert to response models
    by_provider = [ProviderCostSummary(**agg) for agg in aggregates.values()]

    return CostAnalyticsResponse(
        total_cost=total_cost,
        total_requests=total_requests,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        by_provider=by_provider,
    )


# --- Orchestration traces ---


@protected.get("/agent-traces/recent")
async def recent_agent_traces(
    limit: int = Query(default=50, ge=1, le=500),
    run_id: str | None = Query(default=None, max_length=64),
    agent_name: str | None = Query(default=None, max_length=128),
    event_type: str | None = Query(default=None, max_length=64),
):
    events = app.state.trace_buffer.recent(
        limit=limit,
        run_id=run_id,
        agent_name=agent_name,
        event_type=event_type,
    )
    return {
        "events": [event.to_dict() for event in events],
        "count": len(events),
    }


@protected.get("/agent-traces/stream")
async def stream_agent_traces(
    request: Request,
    run_id: str | None = Query(default=None, max_length=64),
    agent_name: str | None = Query(default=None, max_length=128),
    event_type: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=20, ge=0, le=200),
):
    async def event_stream():
        queue, unsubscribe = app.state.trace_buffer.subscribe(
            run_id=run_id,
            agent_name=agent_name,
            event_type=event_type,
        )
        try:
            if limit > 0:
                for event in app.state.trace_buffer.recent(
                    limit=limit,
                    run_id=run_id,
                    agent_name=agent_name,
                    event_type=event_type,
                ):
                    yield f"event: agent_trace\ndata: {json.dumps(event.to_dict())}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield f"event: heartbeat\ndata: {json.dumps({'ts': iso_utc_now()})}\n\n"
                    continue
                yield f"event: agent_trace\ndata: {json.dumps(event.to_dict())}\n\n"
        finally:
            unsubscribe()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@protected.get("/agent-traces/{run_id}")
async def run_agent_traces(
    run_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
):
    events = app.state.trace_buffer.run_events(run_id, limit=limit)
    return {
        "run_id": run_id,
        "events": [event.to_dict() for event in events],
        "count": len(events),
    }


# --- Knowledge Base ---


def _require_mcp_client() -> McpRuntimeClient:
    if not hasattr(app.state, "mcp"):
        raise HTTPException(status_code=503, detail="MCP runtime non initialise")
    return app.state.mcp


def _require_knowledge_base() -> McpRuntimeClient:
    if not knowledge_base_auth_configured():
        raise HTTPException(
            status_code=503,
            detail=knowledge_base_status_detail(),
        )
    return _require_mcp_client()


@protected.get("/knowledge-base/search")
async def knowledge_base_search(q: str):
    if len(q) > 1000:
        raise HTTPException(status_code=400, detail="Search query too long (max 1000 chars)")
    client = _require_knowledge_base()
    try:
        payload = await client.knowledge_base_search(
            q,
            mode="http",
            agent_name="knowledge-base-api",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {
        "results": payload.get("results") or [],
        "provider": payload.get("provider"),
        "provider_label": payload.get("provider_label"),
    }


@protected.get("/knowledge-base/pages/{page_id}")
async def knowledge_base_read_page(page_id: str):
    client = _require_knowledge_base()
    try:
        payload = await client.knowledge_base_read_page(
            page_id,
            mode="http",
            agent_name="knowledge-base-api",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {
        "page_id": page_id,
        "content": payload.get("content") or "",
        "provider": payload.get("provider"),
        "provider_label": payload.get("provider_label"),
    }


@protected.post("/knowledge-base/pages/{page_id}/append")
async def knowledge_base_append(page_id: str, req: KnowledgeBaseAppendRequest):
    client = _require_knowledge_base()
    try:
        payload = await client.knowledge_base_append(
            page_id,
            req.content,
            mode="http",
            agent_name="knowledge-base-api",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {
        "status": "ok",
        "page_id": page_id,
        "provider": payload.get("provider"),
        "provider_label": payload.get("provider_label"),
    }


@protected.post("/knowledge-base/pages")
async def knowledge_base_create_page(req: KnowledgeBaseCreateRequest):
    client = _require_knowledge_base()
    try:
        payload = await client.knowledge_base_create_page(
            req.parent_id,
            req.title,
            req.content,
            mode="http",
            agent_name="knowledge-base-api",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {
        "page_id": payload.get("page_id") or "",
        "provider": payload.get("provider"),
        "provider_label": payload.get("provider_label"),
    }


@protected.post("/agents/knowledge-scribe/run-and-push")
async def run_knowledge_scribe_and_push(req: KnowledgeScribeRequest):
    try:
        agent = app.state.registry.get("knowledge-scribe")
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent 'knowledge-scribe' not found") from None

    messages = [m.model_dump() for m in req.messages]
    prompt = messages[-1]["content"]
    context = messages[:-1] if len(messages) > 1 else None
    response = await agent.run(prompt, router=app.state.router, context=context)

    result = {
        "content": response.content,
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
        "pushed_to_knowledge_base": False,
        "run_id": req.run_id,
    }

    if req.push_to:
        client = _require_knowledge_base()
        trace_run_id = req.run_id or new_run_id()
        try:
            payload = await client.knowledge_base_append(
                req.push_to,
                response.content,
                run_id=trace_run_id,
                mode="knowledge-scribe",
                step=0,
                agent_name="knowledge-scribe",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        result["pushed_to_knowledge_base"] = True
        result["knowledge_base_page_id"] = req.push_to
        result["knowledge_base_provider"] = payload.get("provider")
        result["knowledge_base_provider_label"] = payload.get("provider_label")
        result["run_id"] = trace_run_id

    return result


# --- GitHub dispatch MCP facade ---


@protected.get("/mcp/github-dispatch/workflows")
async def github_dispatch_workflows():
    client = _require_mcp_client()
    try:
        payload = await client.github_list_allowlisted_workflows(
            mode="http",
            agent_name="github-dispatch-api",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc

    return payload


@protected.post("/mcp/github-dispatch/dispatch")
async def github_dispatch_dispatch(req: GitHubDispatchRequest):
    client = _require_mcp_client()
    try:
        payload = await client.github_dispatch_workflow(
            req.workflow_file,
            ref=req.ref,
            inputs=req.inputs,
            run_id=req.run_id,
            mode="github-dispatch",
            step=0,
            agent_name="github-dispatch",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return payload


@protected.post("/mcp/github-dispatch/status")
async def github_dispatch_status(req: GitHubDispatchStatusRequest):
    client = _require_mcp_client()
    try:
        payload = await client.github_get_dispatch_status(
            req.dispatch_id,
            run_id=req.run_id,
            mode="github-dispatch",
            step=0,
            agent_name="github-dispatch",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return payload


# --- FreeCAD / OpenSCAD MCP facade ---


@protected.get("/mcp/freecad/runtime")
async def freecad_runtime_info(run_id: str | None = Query(default=None, max_length=64)):
    client = _require_mcp_client()
    trace_run_id = run_id or new_run_id()
    try:
        payload = await client.freecad_get_runtime_info(
            run_id=trace_run_id,
            mode="freecad",
            step=0,
            agent_name="freecad",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {**payload, "run_id": trace_run_id}


@protected.post("/mcp/freecad/documents")
async def freecad_create_document(req: FreeCADCreateDocumentRequest):
    client = _require_mcp_client()
    trace_run_id = req.run_id or new_run_id()
    try:
        payload = await client.freecad_create_document(
            req.output_path,
            name=req.name,
            primitive=req.primitive,
            length=req.length,
            width=req.width,
            height=req.height,
            run_id=trace_run_id,
            mode="freecad",
            step=0,
            agent_name="freecad",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {**payload, "run_id": trace_run_id}


@protected.post("/mcp/freecad/export")
async def freecad_export_document(req: FreeCADExportDocumentRequest):
    client = _require_mcp_client()
    trace_run_id = req.run_id or new_run_id()
    try:
        payload = await client.freecad_export_document(
            req.document_path,
            req.output_path,
            run_id=trace_run_id,
            mode="freecad",
            step=0,
            agent_name="freecad",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {**payload, "run_id": trace_run_id}


@protected.post("/mcp/freecad/script")
async def freecad_run_script(req: FreeCADRunScriptRequest):
    client = _require_mcp_client()
    trace_run_id = req.run_id or new_run_id()
    try:
        payload = await client.freecad_run_python_script(
            req.script,
            output_path=req.output_path,
            run_id=trace_run_id,
            mode="freecad",
            step=0,
            agent_name="freecad",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {**payload, "run_id": trace_run_id}


@protected.get("/mcp/openscad/runtime")
async def openscad_runtime_info(run_id: str | None = Query(default=None, max_length=64)):
    client = _require_mcp_client()
    trace_run_id = run_id or new_run_id()
    try:
        payload = await client.openscad_get_runtime_info(
            run_id=trace_run_id,
            mode="openscad",
            step=0,
            agent_name="openscad",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {**payload, "run_id": trace_run_id}


@protected.post("/mcp/openscad/validate")
async def openscad_validate_model(req: OpenSCADValidateRequest):
    client = _require_mcp_client()
    trace_run_id = req.run_id or new_run_id()
    try:
        payload = await client.openscad_validate_model(
            req.source,
            run_id=trace_run_id,
            mode="openscad",
            step=0,
            agent_name="openscad",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {**payload, "run_id": trace_run_id}


@protected.post("/mcp/openscad/render")
async def openscad_render_model(req: OpenSCADRenderRequest):
    client = _require_mcp_client()
    trace_run_id = req.run_id or new_run_id()
    try:
        payload = await client.openscad_render_model(
            req.source,
            req.output_path,
            run_id=trace_run_id,
            mode="openscad",
            step=0,
            agent_name="openscad",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {**payload, "run_id": trace_run_id}


@protected.post("/mcp/openscad/export")
async def openscad_export_model(req: OpenSCADRenderRequest):
    client = _require_mcp_client()
    trace_run_id = req.run_id or new_run_id()
    try:
        payload = await client.openscad_export_model(
            req.source,
            req.output_path,
            run_id=trace_run_id,
            mode="openscad",
            step=0,
            agent_name="openscad",
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {**payload, "run_id": trace_run_id}


@protected.get("/mcp/industrial/servers")
async def industrial_mcp_servers():
    client = _require_mcp_client()
    return {
        "items": [
            item for item in client.list_servers() if item.get("key") in INDUSTRIAL_MCP_SERVER_KEYS
        ]
    }


@protected.get("/mcp/industrial/{server_key}/runtime")
async def industrial_mcp_runtime(server_key: str):
    if server_key not in INDUSTRIAL_MCP_SERVER_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown industrial MCP server '{server_key}'")
    client = _require_mcp_client()
    try:
        payload = await _industrial_runtime_payload(client, server_key)
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return payload


@protected.get("/mcp/industrial/{server_key}/resource")
async def industrial_mcp_resource(server_key: str, uri: str = Query(..., min_length=1)):
    if server_key not in INDUSTRIAL_MCP_SERVER_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown industrial MCP server '{server_key}'")
    client = _require_mcp_client()
    try:
        return await client.read_resource(server_key, uri)
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc


@protected.get("/mcp/industrial/platform")
async def industrial_mcp_platform():
    client = _require_mcp_client()
    inventory = [
        item for item in client.list_servers() if item.get("key") in INDUSTRIAL_MCP_SERVER_KEYS
    ]
    runtime_results = await asyncio.gather(
        *(_industrial_runtime_payload(client, str(item.get("key", ""))) for item in inventory),
        return_exceptions=True,
    )
    servers: list[dict[str, Any]] = []
    for item, result in zip(inventory, runtime_results, strict=False):
        if isinstance(result, Exception):
            servers.append(
                {
                    **item,
                    "ok": False,
                    "runtime_ok": False,
                    "error": str(result),
                    "tool_count": 0,
                    "resource_count": 0,
                    "prompt_count": 0,
                }
            )
            continue
        servers.append(
            {
                **item,
                "ok": bool(result.get("ok", False)),
                "runtime_ok": bool(result.get("ok", False)),
                "protocol_version": result.get("protocol_version", ""),
                "server_info": result.get("server_info", {}),
                "tool_count": int(result.get("tool_count", 0) or 0),
                "resource_count": int(result.get("resource_count", 0) or 0),
                "prompt_count": int(result.get("prompt_count", 0) or 0),
                **(
                    {"health": result.get("health")}
                    if isinstance(result.get("health"), dict)
                    else {}
                ),
                **(
                    {"contract": result.get("contract")}
                    if isinstance(result.get("contract"), dict)
                    else {}
                ),
            }
        )

    try:
        topology = await client.read_resource("cockpit-ops", "cockpit://topology")
        topology_payload = topology.get("payload", {}) if isinstance(topology, dict) else {}
    except (McpCallError, McpServerUnavailable):
        topology_payload = {}
    try:
        vendor_contracts = await client.read_resource("cockpit-ops", "cockpit://vendor-contracts")
        vendor_contracts_payload = (
            vendor_contracts.get("payload", {}) if isinstance(vendor_contracts, dict) else {}
        )
    except (McpCallError, McpServerUnavailable):
        vendor_contracts_payload = {}

    return {
        "servers": servers,
        "summary": {
            "server_count": len(servers),
            "runtime_ok_count": sum(1 for item in servers if item.get("runtime_ok")),
            "runtime_error_count": sum(1 for item in servers if not item.get("runtime_ok")),
            "topology_valid": bool(topology_payload.get("valid", False)),
            "vendor_contract_ready_count": int(
                vendor_contracts_payload.get("summary", {}).get("ready_count", 0) or 0
            ),
            "vendor_contract_blocked_count": int(
                vendor_contracts_payload.get("summary", {}).get("blocked_count", 0) or 0
            ),
        },
        "topology": topology_payload,
        "vendor_contracts": vendor_contracts_payload,
    }


def _industrial_health_uri(server_key: str) -> str:
    if server_key == "cockpit-ops":
        return "cockpit://health"
    return f"{server_key}://health"


def _industrial_contract_uri(server_key: str) -> str | None:
    if server_key == "cockpit-ops":
        return None
    return f"{server_key}://contract"


async def _industrial_runtime_payload(client: McpRuntimeClient, server_key: str) -> dict[str, Any]:
    payload = await client.describe_server(server_key)
    health_uri = _industrial_health_uri(server_key)
    try:
        health = await client.read_resource(server_key, health_uri)
        health_payload = health.get("payload") if isinstance(health, dict) else None
        if isinstance(health_payload, dict):
            payload["health"] = health_payload
    except (McpCallError, McpServerUnavailable):
        pass

    contract_uri = _industrial_contract_uri(server_key)
    if contract_uri:
        try:
            contract = await client.read_resource(server_key, contract_uri)
            contract_payload = contract.get("payload") if isinstance(contract, dict) else None
            if isinstance(contract_payload, dict):
                payload["contract"] = contract_payload
        except (McpCallError, McpServerUnavailable):
            pass
    return payload


@protected.post("/mcp/industrial/{server_key}/tools/{tool_name}")
async def industrial_mcp_tool(server_key: str, tool_name: str, req: IndustrialMcpToolRequest):
    if server_key not in INDUSTRIAL_MCP_SERVER_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown industrial MCP server '{server_key}'")
    client = _require_mcp_client()
    trace_run_id = req.run_id or new_run_id()
    try:
        payload = await client.call_tool(
            server_key,
            tool_name,
            req.arguments,
            run_id=trace_run_id,
            mode="industrial-mcp",
            step=0,
            agent_name=server_key,
        )
    except (McpCallError, McpServerUnavailable) as exc:
        raise _mcp_http_exception(exc) from exc
    return {
        "ok": not payload.is_error,
        "run_id": trace_run_id,
        "server_key": server_key,
        "tool_name": tool_name,
        "protocol_version": payload.protocol_version,
        "server_name": payload.server_name,
        "message": payload.message,
        "payload": payload.structured_content,
    }


# --- ComfyUI ---


def _require_comfyui() -> ComfyUIClient:
    if app.state.comfyui is None:
        raise HTTPException(status_code=503, detail="ComfyUI non configure (COMFYUI_URL manquant)")
    return app.state.comfyui


@protected.get("/comfyui/status")
async def comfyui_status():
    client = _require_comfyui()
    return await client.get_system_stats()


@protected.get("/comfyui/queue")
async def comfyui_queue():
    client = _require_comfyui()
    return await client.get_queue_status()


@protected.get("/comfyui/models/{model_type}")
async def comfyui_models(model_type: str = "checkpoints"):
    client = _require_comfyui()
    models = await client.list_models(model_type)
    return {"models": models, "type": model_type}


@protected.post("/comfyui/generate")
async def comfyui_generate(req: ComfyUIGenerateRequest):
    client = _require_comfyui()
    result = await client.generate_image(
        req.prompt,
        req.negative_prompt,
        checkpoint=req.checkpoint,
        width=req.width,
        height=req.height,
        steps=req.steps,
        cfg=req.cfg,
        seed=req.seed,
    )
    return result


@protected.post("/comfyui/workflow")
async def comfyui_workflow(req: ComfyUIWorkflowRequest):
    if not req.workflow or not isinstance(req.workflow, dict):
        raise HTTPException(status_code=400, detail="Workflow must be a non-empty object")
    if len(str(req.workflow)) > 500_000:
        raise HTTPException(status_code=400, detail="Workflow payload too large")
    client = _require_comfyui()
    prompt_id = await client.queue_prompt(req.workflow)
    return {"prompt_id": prompt_id}


@protected.get("/comfyui/history/{prompt_id}")
async def comfyui_history(prompt_id: str):
    client = _require_comfyui()
    return await client.get_history(prompt_id)


@protected.get("/comfyui/image")
async def comfyui_image(filename: str, subfolder: str = "", type: str = "output"):
    from fastapi.responses import Response

    client = _require_comfyui()
    try:
        image_data = await client.get_image(filename, subfolder, type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid image path parameters") from None
    return Response(content=image_data, media_type="image/png")


@protected.post("/comfyui/interrupt")
async def comfyui_interrupt():
    client = _require_comfyui()
    await client.interrupt()
    return {"status": "ok"}


# --- P2P network ---


# --- Benchmark Analytics ---


@protected.get("/v1/analytics/benchmarks")
async def get_benchmark_results(
    domain: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=10, ge=1, le=100),
    order_by: str = Query(default="quality_score", max_length=50),
):
    """
    Get benchmark results leaderboard.

    Query parameters:
    - domain: Filter by domain (optional)
    - limit: Maximum number of results (default: 10, max: 100)
    - order_by: Column to order by (default: quality_score, options: quality_score, latency_p50, cost)

    Returns:
        List of benchmark results with provider, model, domain, and performance metrics
    """
    from mascarade.benchmarks.storage import BenchmarkStorage

    # Validate order_by parameter
    valid_order_by = {"quality_score", "latency_p50", "latency_p95", "cost"}
    if order_by not in valid_order_by:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid order_by parameter. Must be one of: {', '.join(valid_order_by)}"
        )

    storage = BenchmarkStorage()

    try:
        results = storage.query_leaderboard(
            domain=domain,
            limit=limit,
            order_by=order_by,
        )

        return {
            "results": results,
            "count": len(results),
            "filters": {
                "domain": domain,
                "limit": limit,
                "order_by": order_by,
            }
        }
    except Exception as e:
        logger.exception("Failed to query benchmark results")
        raise HTTPException(status_code=500, detail=str(e)) from e


@protected.post("/v1/benchmarks/run", status_code=202)
async def trigger_benchmark_run(req: BenchmarkRunRequest):
    """
    Trigger an on-demand benchmark run.

    Request body:
    - domain: Domain to benchmark (optional, runs all domains if not specified)
    - providers: List of providers to test (optional, tests all providers if not specified)
    - difficulty: Difficulty level to test (optional)
    - limit: Maximum number of prompts per provider (optional)

    Returns:
        202 Accepted with run_id for tracking the benchmark execution
    """
    from mascarade.benchmarks.suite import BenchmarkSuite

    # Initialize benchmark suite with router from app state
    suite = BenchmarkSuite(router=app.state.router)

    # Generate run_id for tracking
    run_id = suite._generate_run_id()

    # Define the background benchmark task
    async def run_benchmark_task():
        """Background task to execute the benchmark."""
        try:
            if req.domain:
                # Run domain-specific benchmark
                logger.info(
                    "Starting domain-specific benchmark (domain=%s, run_id=%s)",
                    req.domain,
                    run_id,
                )
                run = await suite.run_domain_benchmark(
                    domain=req.domain,
                    providers=req.providers,
                    difficulty=req.difficulty,
                    limit=req.limit,
                )
            else:
                # Run full suite benchmark
                logger.info(
                    "Starting full suite benchmark (run_id=%s)",
                    run_id,
                )
                run = await suite.run_full_suite(
                    providers=req.providers,
                    difficulty=req.difficulty,
                    limit=req.limit,
                )

            logger.info(
                "Benchmark completed (run_id=%s, total=%d, successful=%d, failed=%d)",
                run.run_id,
                run.total_benchmarks,
                run.successful_benchmarks,
                run.failed_benchmarks,
            )

            # Store results in ClickHouse
            from mascarade.benchmarks.storage import BenchmarkStorage

            storage = BenchmarkStorage()
            for result in run.results:
                try:
                    storage.write_result(result)
                except Exception as e:
                    logger.warning(
                        "Failed to store benchmark result for %s/%s: %s",
                        result.provider,
                        result.model,
                        e,
                    )

        except Exception as e:
            logger.exception("Benchmark run failed (run_id=%s): %s", run_id, e)

    # Create background task (fire and forget)
    asyncio.create_task(run_benchmark_task())

    return {
        "status": "accepted",
        "run_id": run_id,
        "message": "Benchmark run started in background",
        "filters": {
            "domain": req.domain,
            "providers": req.providers,
            "difficulty": req.difficulty,
            "limit": req.limit,
        },
    }


@protected.post("/v1/benchmarks/webhook/deployment", status_code=200)
async def handle_model_deployment_webhook(webhook: ModelDeploymentWebhook):
    """
    Handle model deployment webhook to trigger automatic benchmarks.

    This endpoint is triggered when a new fine-tuned model is deployed
    and automatically runs benchmarks to evaluate its performance.

    Request body:
    - provider: Provider name (required)
    - model: Model identifier (required)
    - event_type: Type of deployment event (default: "deployment")
    - domain: Domain to benchmark (optional)
    - limit: Maximum number of prompts to test (optional)
    - background: Run benchmark in background (default: true)
    - metadata: Additional event metadata (optional)

    Returns:
        Webhook processing result with trigger status
    """
    from mascarade.benchmarks.triggers import BenchmarkTriggerError

    try:
        # Get trigger instance from app state
        trigger = app.state.benchmark_trigger

        # Process webhook
        result = await trigger.handle_webhook(
            payload={
                "provider": webhook.provider,
                "model": webhook.model,
                "event_type": webhook.event_type,
                "domain": webhook.domain,
                "limit": webhook.limit,
                "background": webhook.background,
                "metadata": webhook.metadata,
            }
        )

        logger.info(
            "Model deployment webhook processed: %s/%s (status=%s)",
            webhook.provider,
            webhook.model,
            result.get("trigger_result", {}).get("status", "unknown"),
        )

        return result

    except BenchmarkTriggerError as exc:
        logger.error("Webhook processing failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error processing webhook")
        raise HTTPException(status_code=500, detail="Internal server error") from exc

@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics for scraping."""
    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        from starlette.responses import Response

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="prometheus_client is not installed",
        )


@protected.get("/device/v1/voice/replies/{reply_id}.wav")
async def device_voice_reply_audio(reply_id: str, request: Request):
    from fastapi.responses import Response as _Response

    service: DeviceVoiceService = request.app.state.device_voice
    audio = service.get_reply_audio(reply_id)
    if audio is None:
        raise HTTPException(status_code=404, detail="Reply audio not found or expired")
    return _Response(content=audio.payload, media_type=audio.content_type)


app.include_router(health_router)
app.include_router(protected)
app.include_router(cluster_protected)


def start():
    import uvicorn

    uvicorn.run(app, host=settings.core_host, port=settings.core_port)


if __name__ == "__main__":
    start()
