"""Protected routes (/v1/*) requiring authentication.

This module creates the protected APIRouter and delegates route registration
to domain-specific modules:
- server_agents: agent CRUD, run, orchestration, templates, cluster, traces
- server_admin: users, api-keys, auth, rate-limits, providers, metrics, analytics, benchmarks, comfyui, device voice
- server_mcp: knowledge-base, github-dispatch, FreeCAD, OpenSCAD, industrial MCP
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

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


_KILL_LIFE_ROOT = Path(os.getenv("KILL_LIFE_ROOT", "/home/clems/Kill_LIFE")).resolve()
_CLI_AGENT_TIMEOUT_S = int(os.getenv("CLI_AGENT_TIMEOUT_S", "60"))


class CliAgentRunRequest(BaseModel):
    agent: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int | None = None


def create_protected_router(app: FastAPI) -> APIRouter:
    """Create and populate the protected APIRouter (/v1/*)."""

    protected = APIRouter(prefix="/v1", dependencies=[Depends(require_auth)])

    # Register routes from domain modules
    register_admin_routes(protected, app)
    register_agent_routes(protected, app)
    register_mcp_routes(protected, app)

    @protected.post("/cli-agents/run")
    async def run_cli_agent(req: CliAgentRunRequest):
        try:
            script = (_KILL_LIFE_ROOT / "tools" / req.agent).resolve()
            script.relative_to(_KILL_LIFE_ROOT / "tools")
        except (ValueError, Exception) as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid agent path: {req.agent!r}"
            ) from exc
        if not script.exists():
            raise HTTPException(
                status_code=404, detail=f"CLI agent not found: {req.agent!r}"
            )
        timeout_s = (req.timeout_ms / 1000) if req.timeout_ms else _CLI_AGENT_TIMEOUT_S
        env = {**dict(os.environ), "KILL_LIFE_ROOT": str(_KILL_LIFE_ROOT), **req.env}
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
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_s
                )
            except TimeoutError:
                proc.kill()
                await proc.communicate()
                raise HTTPException(
                    status_code=504, detail=f"CLI agent timed out after {timeout_s}s"
                ) from None
        except HTTPException:
            raise
        except Exception as exc:
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

    return protected
