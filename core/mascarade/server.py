"""Serveur FastAPI — point d'entree HTTP du core Python."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mascarade.agents import AgentRegistry
from mascarade.agents.skills import register_default_skills
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
from mascarade.router import Router
from mascarade.routers.agents import router as agents_router
from mascarade.routers.auth import router as auth_router
from mascarade.routers.chat import router as chat_router
from mascarade.routers.finetune import router as finetune_router
from mascarade.routers.health import router as health_router
from mascarade.routers.memory import router as memory_router
from mascarade.routers.providers import router as providers_router

logger = logging.getLogger("mascarade.server")

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

    # Store in app state
    app.state.router = router
    app.state.registry = registry
    app.state.orchestrator = orchestrator
    app.state.trace_buffer = trace_buffer
    app.state.cluster = cluster
    app.state.template_registry = template_registry
    app.state.mcp = McpRuntimeClient(trace_buffer=trace_buffer)
    app.state.comfyui = ComfyUIClient() if settings.comfyui_url else None
    app.state.device_voice = DeviceVoiceService(router=router)

    # Load agents
    registry.load()

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

    yield

    # Cleanup
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
        ],
    )

    # Mount routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(agents_router)
    app.include_router(memory_router)
    app.include_router(providers_router)
    app.include_router(finetune_router)

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


def start():
    """Start the server using uvicorn."""
    import uvicorn

    uvicorn.run(app, host=settings.core_host, port=settings.core_port)


if __name__ == "__main__":
    start()
