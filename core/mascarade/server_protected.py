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
import json
import logging
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
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


async def _run_cli_agent_core(req: CliAgentRunRequest) -> dict:
    """Core logic for running a Kill_LIFE CLI agent. Raises HTTPException on errors."""
    try:
        script = (_KILL_LIFE_ROOT / "tools" / req.agent).resolve()
        script.relative_to(_KILL_LIFE_ROOT / "tools")
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid agent path: {req.agent!r}") from exc

    if not script.exists():
        raise HTTPException(status_code=404, detail=f"CLI agent not found: {req.agent!r}")

    timeout_s = (req.timeout_ms / 1000) if req.timeout_ms else _CLI_AGENT_TIMEOUT_S
    env = {**dict(os.environ), "KILL_LIFE_ROOT": str(_KILL_LIFE_ROOT), **req.env}
    # Point shell scripts to a writable venv with Kill_LIFE dependencies installed.
    # /tmp/kl312-venv is bootstrapped once with packages copied from the Kill_LIFE .venv.
    _tmp_venv = Path("/tmp/kl312-venv")
    if _tmp_venv.is_dir() and not req.env.get("VENV_DIR"):
        env.setdefault("VENV_DIR", str(_tmp_venv))
    if script.suffix == ".sh":
        cmd = ["bash", str(script)]
    elif script.suffix == ".py":
        cmd = ["python3", str(script)]
    else:
        cmd = [str(script)]

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
        except TimeoutError as exc:
            proc.kill()
            await proc.communicate()
            raise HTTPException(
                status_code=504, detail=f"CLI agent timed out after {timeout_s}s"
            ) from exc
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


async def run_cli_agent(req: CliAgentRunRequest):
    """Run a Kill_LIFE CLI agent script from KILL_LIFE_ROOT/tools/."""
    return await _run_cli_agent_core(req)


# ─── Agentic loop (ReAct + cli-agents) ───────────────────────────────────────

_AGENTIC_TOOL_SYSTEM = """
## Tool use instructions

You have access to the following tool to execute Kill_LIFE scripts:

  run_cli_agent(agent, args=[])
    Execute a script from Kill_LIFE/tools/.
    - agent: path relative to tools/ e.g. "build_firmware.py" or "hw/hw_check.sh"
    - args: optional list of CLI arguments

Important notes:
- For test_python.sh, always pass args: ["--venv-dir", "/tmp/kl312-venv"] to use the correct Python environment
- Shell scripts (.sh) run with bash, Python scripts (.py) run with python3

To call the tool, output a JSON block with this exact format (and nothing else around it):

```tool_call
{"tool": "run_cli_agent", "agent": "<path>", "args": [...]}
```

The result will be injected as a system message. You may call the tool multiple times.
When done, output your final answer as plain text (no tool_call block).
""".strip()

_TOOL_CALL_RE = re.compile(r"```tool_call\s*\n(\{.*?\})\s*\n```", re.DOTALL)


async def _execute_tool_call(payload: dict) -> str:
    """Execute a parsed tool_call dict, return formatted result string."""
    tool = payload.get("tool")
    if tool != "run_cli_agent":
        return f"[tool error] Unknown tool: {tool!r}"
    agent_path = payload.get("agent", "")
    args = payload.get("args", [])
    timeout_ms = payload.get("timeout_ms")
    try:
        req = CliAgentRunRequest(agent=agent_path, args=args, timeout_ms=timeout_ms)
        result = await _run_cli_agent_core(req)
    except HTTPException as e:
        return f"[tool error] {e.detail}"
    except Exception as e:
        return f"[tool error] {e}"
    status = "ok" if result["ok"] else f"exit {result['exit_code']}"
    parts = [f"[tool result: {agent_path} — {status} in {result['duration_ms']}ms]"]
    if result["output"]:
        parts.append(result["output"].rstrip())
    if result["stderr"]:
        parts.append(f"[stderr]\n{result['stderr'].rstrip()}")
    return "\n".join(parts)


class AgentRunAgenticRequest(BaseModel):
    messages: list[dict[str, str]]
    rag: bool = True
    max_iterations: int = Field(default=6, ge=1, le=20)


def create_protected_router(app: FastAPI) -> APIRouter:
    """Create and populate the protected APIRouter (/v1/*)."""

    protected = APIRouter(prefix="/v1", dependencies=[Depends(require_auth)])

    # Register routes from domain modules
    register_admin_routes(protected, app)
    register_agent_routes(protected, app)
    register_mcp_routes(protected, app)

    @protected.post("/cli-agents/run")
    async def _cli_agents_run(req: CliAgentRunRequest):
        return await _run_cli_agent_core(req)

    @protected.post("/agents/{name}/run-agentic")
    async def _agents_run_agentic(name: str, req: AgentRunAgenticRequest, request: Request):
        try:
            agent = request.app.state.registry.get(name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from exc
        messages = list(req.messages)
        enhanced_system = agent.system_prompt + "\n\n" + _AGENTIC_TOOL_SYSTEM
        tool_calls_log: list[dict] = []
        iterations = 0
        router = request.app.state.router
        content = ""
        response = None
        try:
            from mascarade.agents.base import Agent as _Agent

            while iterations < req.max_iterations:
                iterations += 1
                tmp_agent = _Agent(
                    name=agent.name,
                    description=agent.description,
                    system_prompt=enhanced_system,
                    preferred_provider=agent.preferred_provider,
                    preferred_model=agent.preferred_model,
                    strategy=agent.strategy,
                    routing_policy=agent.routing_policy,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                )
                response = await tmp_agent.run_with_history(messages, router=router)
                content = response.content
                matches = _TOOL_CALL_RE.findall(content)
                if not matches:
                    return {
                        "content": content,
                        "model": response.model,
                        "provider": response.provider,
                        "usage": response.usage,
                        "tool_calls": tool_calls_log,
                        "iterations": iterations,
                    }
                messages.append({"role": "assistant", "content": content})
                results_text: list[str] = []
                for raw in matches:
                    try:
                        payload = json.loads(raw)
                    except Exception as e:
                        results_text.append(f"[tool error] Invalid JSON: {e}")
                        continue
                    tool_calls_log.append(payload)
                    results_text.append(await _execute_tool_call(payload))
                messages.append({"role": "user", "content": "\n\n".join(results_text)})
        except Exception as exc:
            logger.warning("Agentic run failed for %s: %s", name, exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "content": content,
            "model": response.model if response else "",
            "provider": response.provider if response else "",
            "usage": response.usage if response else {},
            "tool_calls": tool_calls_log,
            "iterations": iterations,
            "max_iterations_reached": True,
        }

    return protected
