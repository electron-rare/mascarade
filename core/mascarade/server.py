"""Serveur FastAPI — point d'entree HTTP du core Python."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mascarade.agents import AgentRegistry
from mascarade.agents.skill_registry import SkillRegistry
from mascarade.agents.skills import register_default_skills, register_default_skills_v2
from mascarade.cluster import ClusterManager
from mascarade.config import settings
from mascarade.db.connection import close_db_pool, init_db_pool
from mascarade.device_voice import DeviceVoiceService
from mascarade.integrations.comfyui import ComfyUIClient
from mascarade.mcp import McpRuntimeClient
from mascarade.observability import AgentTraceBuffer
from mascarade.orchestrator import Orchestrator
from mascarade.orchestrator.templates import (
    TemplateRegistry,
    register_builtin_templates,
)
from mascarade.middleware.log_filter import install_secret_masking
from mascarade.middleware.body_limit import BodySizeLimitMiddleware
from mascarade.middleware.rate_limit import RateLimitMiddleware
from mascarade.router import Router
from mascarade.scheduler import ResourceAwareScheduler, HeartbeatMonitor, WorkerState

install_secret_masking()
from mascarade.routers.agents import router as agents_router
from mascarade.routers.skills import router as skills_router
from mascarade.routers.auth import router as auth_router
from mascarade.routers.chat import router as chat_router
from mascarade.routers.finetune import router as finetune_router
from mascarade.routers.health import router as health_router
from mascarade.routers.memory import router as memory_router
from mascarade.routers.providers import router as providers_router
from mascarade.routers.prompt_versioning import router as prompt_versioning_router
from mascarade.routers.cad_mcp import router as cad_mcp_router
from mascarade.routers.admin import router as admin_router
from mascarade.routers.scheduler import router as scheduler_router
from mascarade.scheduler.metrics_exporter import router as metrics_router
from mascarade.routers.analytics import router as analytics_router
from mascarade.routers.a2a import public_router as a2a_public_router, authed_router as a2a_authed_router
from mascarade.routers.ws import router as ws_router
from mascarade.routers.cli_agents import router as cli_agents_router
from mascarade.routers.mistral_agents import router as mistral_agents_router
from mascarade.routers.mistral_capabilities import router as mistral_capabilities_router
from mascarade.routers.mistral_studio import router as mistral_studio_router
from mascarade.routers.knowledge_base import (
    knowledge_base_auth_configured,
    router as knowledge_base_router,
)
from mascarade.benchmarks.storage import BenchmarkStorage  # noqa: F401 — used by tests via patch

logger = logging.getLogger("mascarade.server")

# OpenLLMetry auto-instrumentation (traces LLM calls via OpenTelemetry)
# Install with: uv pip install -e '.[observability]'
try:
    from traceloop.sdk import Traceloop
    Traceloop.init(disable_batch=False)
    logger.info("OpenLLMetry auto-instrumentation enabled")
except ImportError:
    pass

# Import Gradio UI (lazy import to avoid loading gradio if not using finetune extras)
try:
    from mascarade.gradio_ui import create_gradio_app
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False
    logger.warning("Gradio not available. Install with: uv pip install -e '.[finetune]'")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - initializes and cleans up resources."""
    # Initialize core services
    router = Router()
    registry = AgentRegistry()
    register_default_skills(registry)
    skill_registry = SkillRegistry()
    register_default_skills_v2(skill_registry)
    trace_buffer = AgentTraceBuffer()
    cluster = ClusterManager(
        router=router,
        agents_count_provider=lambda: len(registry),
    )
    orchestrator = Orchestrator(
        router=router,
        registry=registry,
        skill_registry=skill_registry,
        trace_buffer=trace_buffer,
        cluster=cluster,
    )
    template_registry = TemplateRegistry()
    register_builtin_templates(template_registry)

    # Initialize distributed scheduler
    scheduler = ResourceAwareScheduler()
    if settings.scheduler_enabled and settings.scheduler_workers:
        for entry in settings.scheduler_workers.split(","):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(":")
            node_id = parts[0]
            port = parts[1] if len(parts) > 1 else "8201"
            worker = WorkerState(node_id=node_id, url=f"http://{entry}" if ":" in entry else f"http://{entry}:{port}")
            scheduler.register_worker(worker)
        logger.info("Scheduler enabled with %d workers", len(scheduler.workers))

    heartbeat = HeartbeatMonitor(
        scheduler.workers,
        interval=settings.scheduler_heartbeat_interval,
    )

    # Store in app state
    # Only set if not already set (to preserve test mocks)
    if not hasattr(app.state, "router") or app.state.router is None:
        app.state.router = router
    if not hasattr(app.state, "registry") or app.state.registry is None:
        app.state.registry = registry
    if not hasattr(app.state, "orchestrator") or app.state.orchestrator is None:
        app.state.orchestrator = orchestrator
    if not hasattr(app.state, "trace_buffer") or app.state.trace_buffer is None:
        app.state.trace_buffer = trace_buffer
    if not hasattr(app.state, "cluster") or app.state.cluster is None:
        app.state.cluster = cluster
    if not hasattr(app.state, "skill_registry") or app.state.skill_registry is None:
        app.state.skill_registry = skill_registry
    if not hasattr(app.state, "template_registry") or app.state.template_registry is None:
        app.state.template_registry = template_registry
    if not hasattr(app.state, "mcp") or app.state.mcp is None:
        app.state.mcp = McpRuntimeClient(trace_buffer=trace_buffer)
    if not hasattr(app.state, "comfyui"):
        app.state.comfyui = ComfyUIClient() if settings.comfyui_url else None
    if not hasattr(app.state, "device_voice") or app.state.device_voice is None:
        app.state.device_voice = DeviceVoiceService(router=router)
    if not hasattr(app.state, "scheduler") or app.state.scheduler is None:
        app.state.scheduler = scheduler
    if not hasattr(app.state, "heartbeat_monitor") or app.state.heartbeat_monitor is None:
        app.state.heartbeat_monitor = heartbeat

    # Load persisted data
    registry.load()
    skill_registry.load()

    # Initialize database pool if configured
    if settings.database_url:
        try:
            await init_db_pool()
            logger.info("Database pool initialized")
        except Exception as e:
            logger.warning("Failed to initialize database pool: %s", e)

    # Start P2P node (auto-selects backend)
    await cluster.start_p2p()

    # Start health checks for all registered providers
    router.health_monitor.start_health_checks(list(router._providers.values()))
    
    # Initialize health endpoint response
    app.state.health_status = "healthy"

    # Start distributed scheduler heartbeat
    if settings.scheduler_enabled and scheduler.workers:
        await heartbeat.start()
        # Wire scheduler into router for distributed dispatch
        router.scheduler = scheduler
        logger.info("Distributed scheduler heartbeat started")

    yield

    # Cleanup
    if hasattr(app.state, "heartbeat_monitor") and app.state.heartbeat_monitor:
        await app.state.heartbeat_monitor.stop()
    await router.health_monitor.stop_health_checks()
    await cluster.stop_p2p()
    await cluster.close()

    if app.state.comfyui is not None:
        await app.state.comfyui.close()

    if settings.database_url:
        await close_db_pool()
        logger.info("Database pool closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Mascarade Core",
        version="0.1.0",
        description=(
            "Personal agentic orchestration system - Python core API\n\n"
            "Provides LLM routing, agent orchestration, memory management, "
            "and OpenAI-compatible chat completions."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {
                "name": "health",
                "description": "Health checks and system status monitoring",
            },
            {
                "name": "chat",
                "description": "OpenAI-compatible chat completion endpoints",
            },
            {
                "name": "agents",
                "description": "Agent management and orchestration",
            },
            {
                "name": "skills",
                "description": "Skill management and agent assignment",
            },
            {
                "name": "memory",
                "description": "Memory and knowledge base operations",
            },
            {
                "name": "providers",
                "description": "LLM provider management and configuration",
            },
            {
                "name": "auth",
                "description": "Authentication and authorization",
            },
            {
                "name": "finetune",
                "description": "Fine-tuning job management",
            },
            {
                "name": "a2a",
                "description": "A2A (Agent-to-Agent) protocol — discovery and task delegation",
            },
        ],
    )

    # Pre-initialize state attributes so tests can patch them before lifespan runs
    app.state.router = None
    app.state.registry = None
    app.state.orchestrator = None
    app.state.trace_buffer = None
    app.state.cluster = None
    app.state.skill_registry = None
    app.state.template_registry = None
    app.state.mcp = None
    app.state.comfyui = None
    app.state.device_voice = None
    app.state.scheduler = None
    app.state.heartbeat_monitor = None

    # Mount routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(agents_router)
    app.include_router(skills_router)
    app.include_router(memory_router)
    app.include_router(providers_router)
    app.include_router(finetune_router)
    app.include_router(prompt_versioning_router)
    app.include_router(cad_mcp_router)
    app.include_router(knowledge_base_router)
    app.include_router(admin_router)
    app.include_router(scheduler_router)
    app.include_router(metrics_router)
    app.include_router(analytics_router)
    app.include_router(a2a_public_router)
    app.include_router(a2a_authed_router)
    app.include_router(ws_router)
    app.include_router(cli_agents_router)
    app.include_router(mistral_agents_router)
    app.include_router(mistral_capabilities_router)
    app.include_router(mistral_studio_router)

    # Mount Gradio UI for fine-tuning (if available)
    if GRADIO_AVAILABLE:
        try:
            import gradio as gr
            gradio_app = create_gradio_app()
            app = gr.mount_gradio_app(app, gradio_app, path="/finetune")
            logger.info("Gradio fine-tuning UI mounted at /finetune")
        except Exception as e:
            logger.warning("Failed to mount Gradio UI: %s", e)

    return app


# Create app instance
app = create_app()
app.add_middleware(RateLimitMiddleware, requests_per_minute=60, burst=120)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=10 * 1024 * 1024)


def start():
    """Start the server using uvicorn."""
    import uvicorn

    uvicorn.run(app, host=settings.core_host, port=settings.core_port)


if __name__ == "__main__":
    start()
