"""Serveur FastAPI — point d'entree HTTP du core Python."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mascarade.agents import AgentRegistry
from mascarade.agents.skill_registry import SkillRegistry
from mascarade.agents.skills import register_default_skills
from mascarade.cluster import ClusterManager
from mascarade.config import settings
from mascarade.db.connection import close_db_pool, init_db_pool
from mascarade.device_voice import DeviceVoiceService
from mascarade.integrations.comfyui import ComfyUIClient
from mascarade.mcp import McpRuntimeClient
from mascarade.observability import AgentTraceBuffer
from mascarade.ollama_compat import mount_ollama_compat
from mascarade.orchestrator import Orchestrator
from mascarade.orchestrator.templates import (
    TemplateRegistry,
    register_builtin_templates,
)
from mascarade.router import Router
from mascarade.server_cluster import create_cluster_router
from mascarade.server_protected import create_protected_router
from mascarade.server_routes import register_public_routes

logger = logging.getLogger("mascarade.server")


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
    template_registry.load()

    skill_registry = SkillRegistry()
    app.state.skill_registry = skill_registry
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

    # Initialize OpenLLMetry (automatic OTel instrumentation of LLM providers)
    if settings.openllmetry_enabled:
        from mascarade.observability.openllmetry import init_openllmetry

        init_openllmetry()

    # Initialize database pool if DATABASE_URL is configured
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
    if getattr(app.state, "qdrant", None) is not None:
        await app.state.qdrant.close()


app = FastAPI(title="Mascarade Core", version="0.3.0", lifespan=lifespan)

# CORS — restrict origins via CORS_ALLOWED_ORIGINS env var (comma-separated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins.split(",") if settings.cors_allowed_origins else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register routes ---

register_public_routes(app)
app.include_router(create_protected_router(app))
app.include_router(create_cluster_router(app))

# OpenAI-compatible audio endpoints for ESP32-S3-BOX-3 (no auth required)
from mascarade.routers.openai_audio import router as openai_audio_router

app.include_router(openai_audio_router)

# KiCad + SPICE MCP endpoints
from mascarade.routers.kicad_mcp import router as kicad_mcp_router

app.include_router(kicad_mcp_router)

# Eval harness (lm-evaluation-harness) endpoints
from mascarade.routers.eval import router as eval_router

app.include_router(eval_router)

# Node Engine — graph CRUD, execution, catalog
from mascarade.routers.node_engine import router as node_engine_router

app.include_router(node_engine_router)

# Node Catalog — DAG node discovery and registration
from mascarade.routers.nodes import router as nodes_router

app.include_router(nodes_router)

# Coordination API — multi-agent selection and execution
from mascarade.routers.coordination import router as coordination_router

app.include_router(coordination_router)

# Mount Ollama-compatible API (fake Ollama backed by Mascarade Router + P2P)
mount_ollama_compat(app)


def start():
    import uvicorn

    uvicorn.run(app, host=settings.core_host, port=settings.core_port)


if __name__ == "__main__":
    start()
