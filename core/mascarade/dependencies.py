"""Shared dependency injection functions for FastAPI routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

# Import authentication dependencies directly (needed for re-export)
from mascarade.auth import get_current_user as _get_current_user
from mascarade.auth import require_admin as _require_admin
from mascarade.db.models import User

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from mascarade.agents import AgentRegistry
    from mascarade.cluster import ClusterManager
    from mascarade.mcp import McpRuntimeClient
    from mascarade.observability import AgentTraceBuffer
    from mascarade.orchestrator import Orchestrator
    from mascarade.orchestrator.templates import TemplateRegistry
    from mascarade.router import Router

__all__ = [
    "get_router",
    "get_registry",
    "get_orchestrator",
    "get_cluster",
    "get_trace_buffer",
    "get_template_registry",
    "get_mcp_client",
    "get_current_user",
    "require_admin",
]


# --- Re-export auth dependencies ---


async def get_current_user(*args, **kwargs) -> User:
    """Get the current authenticated user.

    Re-exported from mascarade.auth for convenient access.

    Returns:
        User object for the authenticated user

    Raises:
        HTTPException: 401 if authentication fails
    """
    return await _get_current_user(*args, **kwargs)


async def require_admin(*args, **kwargs) -> User:
    """Require admin privileges for the current user.

    Re-exported from mascarade.auth for convenient access.

    Returns:
        User object if the user is an admin

    Raises:
        HTTPException: 403 if the user does not have admin privileges
    """
    return await _require_admin(*args, **kwargs)


# --- Application state dependencies ---


def get_router(request: Request) -> Router:
    """Get the Router instance from application state.

    Args:
        request: FastAPI request object

    Returns:
        Router instance for LLM provider routing
    """
    return request.app.state.router


def get_registry(request: Request) -> AgentRegistry:
    """Get the AgentRegistry instance from application state.

    Args:
        request: FastAPI request object

    Returns:
        AgentRegistry instance containing all registered agents
    """
    return request.app.state.registry


def get_orchestrator(request: Request) -> Orchestrator:
    """Get the Orchestrator instance from application state.

    Args:
        request: FastAPI request object

    Returns:
        Orchestrator instance for multi-agent task execution
    """
    return request.app.state.orchestrator


def get_cluster(request: Request) -> ClusterManager:
    """Get the ClusterManager instance from application state.

    Args:
        request: FastAPI request object

    Returns:
        ClusterManager instance for P2P cluster coordination
    """
    return request.app.state.cluster


def get_trace_buffer(request: Request) -> AgentTraceBuffer:
    """Get the AgentTraceBuffer instance from application state.

    Args:
        request: FastAPI request object

    Returns:
        AgentTraceBuffer instance for tracing agent executions
    """
    return request.app.state.trace_buffer


def get_template_registry(request: Request) -> TemplateRegistry:
    """Get the TemplateRegistry instance from application state.

    Args:
        request: FastAPI request object

    Returns:
        TemplateRegistry instance for orchestration templates
    """
    return request.app.state.template_registry


def get_mcp_client(request: Request) -> McpRuntimeClient:
    """Get the McpRuntimeClient instance from application state.

    Args:
        request: FastAPI request object

    Returns:
        McpRuntimeClient instance for MCP protocol communication
    """
    return request.app.state.mcp
