"""Protected routes (/v1/*) requiring authentication.

This module creates the protected APIRouter and delegates route registration
to domain-specific modules:
- server_agents: agent CRUD, run, orchestration, templates, cluster, traces
- server_admin: users, api-keys, auth, rate-limits, providers, metrics, analytics, benchmarks, comfyui, device voice
- server_mcp: knowledge-base, github-dispatch, FreeCAD, OpenSCAD, industrial MCP
"""

from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, Depends, FastAPI

from mascarade.agents import Agent, AgentRegistry
from mascarade.auth import require_auth
from mascarade.server_admin import register_admin_routes
from mascarade.server_agents import register_agent_routes
from mascarade.server_mcp import register_mcp_routes

logger = logging.getLogger("mascarade.server")


def hash_api_key(key: str) -> str:
    """Hash API key for author tracking (returns first 8 chars of SHA-256)."""
    if not key:
        return ""
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def _serialize_agent(agent: Agent, registry: AgentRegistry) -> dict[str, object]:
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
        "builtin": registry.is_builtin(agent.name),
    }


def create_protected_router(app: FastAPI) -> APIRouter:
    """Create and populate the protected APIRouter (/v1/*)."""

    protected = APIRouter(prefix="/v1", dependencies=[Depends(require_auth)])

    # Register routes from domain modules
    register_admin_routes(protected, app)
    register_agent_routes(protected, app)
    register_mcp_routes(protected, app)

    return protected
