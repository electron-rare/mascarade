"""Internal stdio MCP client for local Kill_LIFE launchers."""

from __future__ import annotations

import asyncio
import ast
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mascarade.config import settings
from mascarade.observability import AgentTraceBuffer

logger = logging.getLogger("mascarade.mcp.client")

DEFAULT_PROTOCOL_VERSION = "2025-03-26"
def _resolve_default_dir(env_var: str, fallback_name: str) -> Path:
    """Resolve a directory from env var, falling back to ~/fallback_name."""
    raw = os.getenv(env_var, "")
    if raw:
        return Path(raw).resolve()
    return Path.home().joinpath(fallback_name).resolve()


DEFAULT_MASCARADE_DIR = _resolve_default_dir("MASCARADE_DIR", "mascarade")
DEFAULT_KILL_LIFE_ROOT = _resolve_default_dir("KILL_LIFE_ROOT", "Kill_LIFE")
DEFAULT_AGENT_FACTORY_COCKPIT_DIR = _resolve_default_dir(
    "AGENT_FACTORY_COCKPIT_DIR", "agent-factory-cockpit"
)
DEFAULT_MASCARADE_ENV_FILE = Path(
    os.getenv("MASCARADE_ENV_FILE", str(DEFAULT_MASCARADE_DIR / ".env"))
).resolve()
_FREECAD_BLOCKED_SNIPPETS = (
    "import os",
    "from os",
    "import subprocess",
    "from subprocess",
    "import socket",
    "from socket",
    "__import__",
    "eval(",
    "exec(",
    "open(",
)
_FREECAD_ALLOWED_IMPORT_ROOTS = {
    "FreeCAD",
    "App",
    "Part",
    "math",
    "json",
}
_FREECAD_BLOCKED_MODULE_NAMES = {
    "os",
    "subprocess",
    "socket",
    "pathlib",
    "sys",
    "shutil",
    "builtins",
}
_FREECAD_BLOCKED_CALLS = {
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "help",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
}


@dataclass(slots=True)
class McpServerDefinition:
    key: str
    launcher: Path | None = None
    command: tuple[str, ...] | None = None
    cwd: Path | None = None
    timeout_s: float = 45.0
    transport: str = "stdio"
    label: str | None = None
    description: str | None = None
    url: str | None = None


@dataclass(slots=True)
class McpToolResult:
    server_key: str
    tool_name: str
    structured_content: dict[str, Any]
    message: str
    protocol_version: str | None
    server_name: str | None
    is_error: bool
    latency_ms: float
    transport: str = "stdio"


class McpError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        server_key: str,
        tool_name: str | None = None,
        protocol_version: str | None = None,
        transport: str = "stdio",
        latency_ms: float | None = None,
        structured_content: dict[str, Any] | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.server_key = server_key
        self.tool_name = tool_name
        self.protocol_version = protocol_version
        self.transport = transport
        self.latency_ms = latency_ms
        self.structured_content = structured_content or {}
        self.error_code = error_code


class McpServerUnavailable(McpError):
    """The target MCP server could not be started or initialized."""


class McpCallError(McpError):
    """The MCP server answered, but the requested tool call failed."""


def _message_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    return text
    return ""


def _normalize_scope(
    *,
    project_id: str | None = None,
    federation_scope: list[str] | tuple[str, ...] | None = None,
    knowledge_scope: str = "project",
) -> tuple[str, list[str], str]:
    normalized_project = (project_id or settings.mascarade_project_id).strip() or "default"
    normalized_scope = (knowledge_scope or "project").strip().lower() or "project"
    if normalized_scope not in {"project", "federated"}:
        raise ValueError(f"Unsupported knowledge_scope: {knowledge_scope}")

    cleaned_federation = [
        item.strip()
        for item in (federation_scope or [])
        if str(item).strip()
    ]
    if normalized_scope == "project":
        cleaned_federation = [normalized_project]
    elif not cleaned_federation:
        raise ValueError("federation_scope is required when knowledge_scope is federated")
    elif normalized_project not in cleaned_federation:
        cleaned_federation = [normalized_project, *cleaned_federation]

    return normalized_project, list(dict.fromkeys(cleaned_federation)), normalized_scope


async def _read_message(
    stdout: asyncio.StreamReader,
) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    first_line: bytes | None = None
    while True:
        line = await stdout.readline()
        if not line:
            return None
        if first_line is None:
            first_line = line
            if line.lstrip().startswith(b"{"):
                return json.loads(line.decode("utf-8"))
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("utf-8").partition(":")
        headers[key.strip().lower()] = value.strip()

    content_length = int(headers.get("content-length", "0") or "0")
    if content_length <= 0:
        return None

    body = await stdout.readexactly(content_length)
    return json.loads(body.decode("utf-8"))


async def _write_message(
    stdin: asyncio.StreamWriter,
    payload: dict[str, Any],
) -> None:
    body = json.dumps(payload).encode("utf-8")
    stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode())
    stdin.write(body)
    await stdin.drain()


def _validate_freecad_script(script: str) -> None:
    if len(script) > 20_000:
        raise ValueError("FreeCAD script too large (max 20,000 chars)")

    lowered = script.lower()
    for snippet in _FREECAD_BLOCKED_SNIPPETS:
        if snippet in lowered:
            raise ValueError(f"FreeCAD script contains blocked pattern: {snippet}")

    try:
        tree = ast.parse(script, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"FreeCAD script syntax error: {exc.msg}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in _FREECAD_ALLOWED_IMPORT_ROOTS:
                    raise ValueError(f"FreeCAD script blocked import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").strip()
            root = module.split(".", 1)[0] if module else ""
            if node.level != 0 or root not in _FREECAD_ALLOWED_IMPORT_ROOTS:
                raise ValueError(f"FreeCAD script blocked import-from: {module or '<relative>'}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _FREECAD_BLOCKED_CALLS:
                raise ValueError(f"FreeCAD script blocked function call: {node.func.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                raise ValueError(f"FreeCAD script blocked dunder attribute: {node.attr}")
            if isinstance(node.value, ast.Name) and node.value.id in _FREECAD_BLOCKED_MODULE_NAMES:
                raise ValueError(f"FreeCAD script blocked module access: {node.value.id}.{node.attr}")
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load) and (
                node.id in _FREECAD_BLOCKED_MODULE_NAMES or node.id.startswith("__")
            ):
                raise ValueError(f"FreeCAD script blocked name usage: {node.id}")


class McpRuntimeClient:
    """Thin async stdio client for local MCP launchers."""

    def __init__(
        self,
        *,
        trace_buffer: AgentTraceBuffer | None = None,
        mascarade_dir: Path | None = None,
        kill_life_root: Path | None = None,
        agent_factory_cockpit_dir: Path | None = None,
        mascarade_env_file: Path | None = None,
    ) -> None:
        self.trace_buffer = trace_buffer
        self.mascarade_dir = (mascarade_dir or DEFAULT_MASCARADE_DIR).resolve()
        self.kill_life_root = (kill_life_root or DEFAULT_KILL_LIFE_ROOT).resolve()
        self.agent_factory_cockpit_dir = (
            agent_factory_cockpit_dir or DEFAULT_AGENT_FACTORY_COCKPIT_DIR
        ).resolve()
        self.mascarade_env_file = (mascarade_env_file or DEFAULT_MASCARADE_ENV_FILE).resolve()
        self._servers: dict[str, McpServerDefinition] = {
            "knowledge-base": McpServerDefinition(
                key="knowledge-base",
                launcher=self.kill_life_root / "tools" / "run_knowledge_base_mcp.sh",
                timeout_s=35.0,
            ),
            "github-dispatch": McpServerDefinition(
                key="github-dispatch",
                launcher=self.kill_life_root / "tools" / "run_github_dispatch_mcp.sh",
                timeout_s=45.0,
            ),
            "freecad": McpServerDefinition(
                key="freecad",
                launcher=self.kill_life_root / "tools" / "run_freecad_mcp.sh",
                timeout_s=60.0,
            ),
            "openscad": McpServerDefinition(
                key="openscad",
                launcher=self.kill_life_root / "tools" / "run_openscad_mcp.sh",
                timeout_s=60.0,
            ),
            "kicad": McpServerDefinition(
                key="kicad",
                launcher=self.kill_life_root / "tools" / "hw" / "run_kicad_mcp.sh",
                timeout_s=60.0,
            ),
        }
        self._register_industrial_servers()
        self._register_graphiti_server()

    def _register_industrial_servers(self) -> None:
        if not self.agent_factory_cockpit_dir.exists():
            return
        industrial_metadata = {
            "cockpit-ops": (
                "Industrial Cockpit Ops",
                "Operator control plane for runs, alerts, topology, vendor contracts, and governance signals.",
            ),
            "plm": (
                "PLM MCP",
                "Product lifecycle management contract surface for governed product records and release traces.",
            ),
            "qms": (
                "QMS MCP",
                "Quality management surface for validation packs, deviations, and sign-off posture.",
            ),
            "mes": (
                "MES MCP",
                "Manufacturing execution surface for build dispatch and work-order status contracts.",
            ),
            "erp": (
                "ERP MCP",
                "Enterprise release surface for release publication and governed change-order contracts.",
            ),
            "wms": (
                "WMS MCP",
                "Warehouse logistics surface for pick waves, shipment release, and inventory holds.",
            ),
            "dcs": (
                "DCS MCP",
                "Critical-boundary surface for governed read snapshots and write-request escalation paths.",
            ),
        }
        for key, (label, description) in industrial_metadata.items():
            self._servers[key] = McpServerDefinition(
                key=key,
                command=(
                    "python3",
                    "-m",
                    "agent_factory_cockpit.cli",
                    "mcp-stdio",
                    key,
                    "--actor",
                    "mascarade-mcp",
                    "--auth-mode",
                    "token",
                ),
                cwd=self.agent_factory_cockpit_dir,
                timeout_s=45.0,
                label=label,
                description=description,
            )

    def _register_graphiti_server(self) -> None:
        if os.getenv("GRAPHITI_ENABLED", "").lower() not in ("true", "1", "yes"):
            return
        graphiti_url = os.getenv(
            "GRAPHITI_MCP_URL", "http://mascarade-graphiti-mcp:8000"
        )
        self._servers["graphiti"] = McpServerDefinition(
            key="graphiti",
            transport="http",
            url=graphiti_url,
            timeout_s=30.0,
            label="Graphiti Knowledge Graph",
            description="Semantic knowledge graph for entity relationships and episodic memory.",
        )

    def _server(self, server_key: str) -> McpServerDefinition:
        try:
            return self._servers[server_key]
        except KeyError as exc:  # pragma: no cover - programming error
            raise McpServerUnavailable(
                f"Unknown MCP server '{server_key}'",
                server_key=server_key,
            ) from exc

    def _server_command(self, server: McpServerDefinition) -> tuple[tuple[str, ...], Path]:
        if server.command:
            return tuple(server.command), (server.cwd or self.mascarade_dir)
        launcher = server.launcher
        if launcher is None or not launcher.exists():
            raise McpServerUnavailable(
                f"MCP launcher missing for {server.key}: {launcher}",
                server_key=server.key,
                transport=server.transport,
            )
        return ("bash", str(launcher)), (server.cwd or launcher.parent)

    def list_servers(self) -> list[dict[str, Any]]:
        items = []
        for key, server in sorted(self._servers.items()):
            items.append(
                {
                    "key": key,
                    "label": server.label or key,
                    "description": server.description or "",
                    "transport": server.transport,
                    "timeout_s": server.timeout_s,
                    "cwd": str(server.cwd or ""),
                    "command": list(server.command) if server.command else [],
                    "launcher": str(server.launcher) if server.launcher else "",
                }
            )
        return items

    def _trace(
        self,
        *,
        run_id: str | None,
        mode: str,
        step: int,
        agent_name: str | None,
        event_type: str,
        server_key: str,
        tool_name: str,
        status: str,
        severity: str = "info",
        latency_ms: float | None = None,
        protocol_version: str | None = None,
        error: str | None = None,
        content_excerpt: str | None = None,
        transport: str = "stdio",
    ) -> None:
        if not self.trace_buffer or not run_id:
            return
        self.trace_buffer.record(
            run_id=run_id,
            mode=mode,
            event_type=event_type,
            step=step,
            severity=severity,
            agent_name=agent_name,
            content_excerpt=content_excerpt,
            error=error,
            mcp_server=server_key,
            mcp_tool=tool_name,
            mcp_status=status,
            mcp_transport=transport,
            mcp_latency_ms=latency_ms,
            mcp_protocol_version=protocol_version,
        )

    async def call_tool(
        self,
        server_key: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
        timeout_s: float | None = None,
    ) -> McpToolResult:
        server = self._server(server_key)
        if server.transport == "http":
            return await self.call_tool_http(
                server_key,
                tool_name,
                arguments,
                run_id=run_id,
                mode=mode,
                step=step,
                agent_name=agent_name,
                timeout_s=timeout_s,
            )
        command, cwd = self._server_command(server)

        env = os.environ.copy()
        env["MASCARADE_DIR"] = str(self.mascarade_dir)
        env["MASCARADE_ENV_FILE"] = str(self.mascarade_env_file)
        env["KILL_LIFE_ROOT"] = str(self.kill_life_root)
        env["AGENT_FACTORY_COCKPIT_DIR"] = str(self.agent_factory_cockpit_dir)
        existing_pythonpath = env.get("PYTHONPATH", "").strip()
        env["PYTHONPATH"] = (
            f"{self.agent_factory_cockpit_dir}:{existing_pythonpath}"
            if existing_pythonpath
            else str(self.agent_factory_cockpit_dir)
        )

        started = time.perf_counter()
        self._trace(
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
            event_type="mcp_call_started",
            server_key=server_key,
            tool_name=tool_name,
            status="started",
            transport="http",
        )
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(cwd),
        )
        protocol_version: str | None = None
        server_name: str | None = None
        timeout = timeout_s or server.timeout_s

        async def _request(message: dict[str, Any]) -> dict[str, Any]:
            if proc.stdin is None or proc.stdout is None:
                raise McpServerUnavailable(
                    f"MCP server '{server_key}' stdin/stdout unavailable",
                    server_key=server_key,
                    tool_name=tool_name,
                    protocol_version=protocol_version,
                    transport=server.transport,
                )
            await _write_message(proc.stdin, message)
            response = await asyncio.wait_for(_read_message(proc.stdout), timeout=timeout)
            if response is None:
                stderr_excerpt = ""
                try:
                    await asyncio.wait_for(proc.wait(), timeout=0.5)
                except TimeoutError:
                    pass
                if proc.stderr is not None:
                    stderr_excerpt = (
                        (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
                    )
                detail = f"MCP server '{server_key}' returned EOF"
                if stderr_excerpt:
                    detail = f"{detail}: {stderr_excerpt}"
                raise McpServerUnavailable(
                    detail,
                    server_key=server_key,
                    tool_name=tool_name,
                    protocol_version=protocol_version,
                    transport=server.transport,
                )
            if "error" in response:
                error = response["error"] or {}
                raise McpServerUnavailable(
                    str(error.get("message") or "MCP request failed"),
                    server_key=server_key,
                    tool_name=tool_name,
                    protocol_version=protocol_version,
                    transport=server.transport,
                    error_code=str(error.get("code") or ""),
                )
            return response

        try:
            initialize = await _request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {},
                }
            )
            result = initialize.get("result") or {}
            protocol_version = str(result.get("protocolVersion") or "")
            server_info = result.get("serverInfo") or {}
            if isinstance(server_info, dict):
                server_name = str(server_info.get("name") or "").strip() or None

            if proc.stdin is None:
                raise McpServerUnavailable(
                    f"MCP server '{server_key}' stdin unavailable after initialize",
                    server_key=server_key,
                    tool_name=tool_name,
                    protocol_version=protocol_version,
                    transport=server.transport,
                )
            await _write_message(
                proc.stdin,
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
            )

            tool_response = await _request(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments or {},
                    },
                }
            )
            tool_result = tool_response.get("result") or {}
            latency_ms = (time.perf_counter() - started) * 1000
            structured = tool_result.get("structuredContent")
            if not isinstance(structured, dict):
                structured = {}
            message = _message_text(tool_result) or tool_name
            is_error = bool(tool_result.get("isError"))
            if is_error:
                error_code = None
                if isinstance(structured.get("error"), dict):
                    error_code = str(structured["error"].get("code") or "").strip() or None
                self._trace(
                    run_id=run_id,
                    mode=mode,
                    step=step,
                    agent_name=agent_name,
                    event_type="mcp_call_failed",
                    server_key=server_key,
                    tool_name=tool_name,
                    status="error",
                    severity="error",
                    latency_ms=latency_ms,
                    protocol_version=protocol_version,
                    error=message,
                )
                raise McpCallError(
                    message,
                    server_key=server_key,
                    tool_name=tool_name,
                    protocol_version=protocol_version,
                    transport=server.transport,
                    latency_ms=latency_ms,
                    structured_content=structured,
                    error_code=error_code,
                )

            self._trace(
                run_id=run_id,
                mode=mode,
                step=step,
                agent_name=agent_name,
                event_type="mcp_call_completed",
                server_key=server_key,
                tool_name=tool_name,
                status="ok",
                latency_ms=latency_ms,
                protocol_version=protocol_version,
                content_excerpt=message,
            )
            return McpToolResult(
                server_key=server_key,
                tool_name=tool_name,
                structured_content=structured,
                message=message,
                protocol_version=protocol_version,
                server_name=server_name,
                is_error=False,
                latency_ms=latency_ms,
                transport=server.transport,
            )
        except TimeoutError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            self._trace(
                run_id=run_id,
                mode=mode,
                step=step,
                agent_name=agent_name,
                event_type="mcp_call_failed",
                server_key=server_key,
                tool_name=tool_name,
                status="timeout",
                severity="error",
                latency_ms=latency_ms,
                protocol_version=protocol_version,
                error=f"MCP timeout after {timeout:.1f}s",
            )
            raise McpServerUnavailable(
                f"MCP timeout after {timeout:.1f}s",
                server_key=server_key,
                tool_name=tool_name,
                protocol_version=protocol_version,
                transport=server.transport,
                latency_ms=latency_ms,
                error_code="timeout",
            ) from exc
        finally:
            stderr_text = ""
            if proc.stdin is not None:
                proc.stdin.close()
                try:
                    await proc.stdin.wait_closed()
                except (OSError, RuntimeError) as exc:
                    logger.debug("Failed to close MCP stdin cleanly: %s", exc)
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except TimeoutError:
                proc.kill()
                await proc.wait()
            if proc.stderr is not None:
                stderr_text = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
            if proc.returncode not in (0, None) and not stderr_text:
                stderr_text = f"launcher exited with code {proc.returncode}"
            if proc.returncode not in (0, None) and stderr_text:
                # Preserve stderr on unexpected launcher exits when the request path
                # did not already surface an MCP-level error.
                pass

    async def call_tool_http(
        self,
        server_key: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
        timeout_s: float | None = None,
    ) -> McpToolResult:
        import httpx

        server = self._server(server_key)
        url = server.url
        if not url:
            raise McpServerUnavailable(
                f"MCP server '{server_key}' has no URL configured",
                server_key=server_key,
                transport="http",
            )
        timeout = timeout_s or server.timeout_s
        started = time.perf_counter()
        self._trace(
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
            event_type="mcp_call_started",
            server_key=server_key,
            tool_name=tool_name,
            status="started",
        )
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as http:
                resp = await http.post(url, json=payload)
                resp.raise_for_status()
                body = resp.json()
        except httpx.TimeoutException as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            self._trace(
                run_id=run_id,
                mode=mode,
                step=step,
                agent_name=agent_name,
                event_type="mcp_call_failed",
                server_key=server_key,
                tool_name=tool_name,
                status="timeout",
                severity="error",
                latency_ms=latency_ms,
                error=f"HTTP timeout after {timeout:.1f}s",
                transport="http",
            )
            raise McpServerUnavailable(
                f"HTTP timeout after {timeout:.1f}s",
                server_key=server_key,
                tool_name=tool_name,
                transport="http",
                latency_ms=latency_ms,
                error_code="timeout",
            ) from exc
        except httpx.HTTPError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            self._trace(
                run_id=run_id,
                mode=mode,
                step=step,
                agent_name=agent_name,
                event_type="mcp_call_failed",
                server_key=server_key,
                tool_name=tool_name,
                status="error",
                severity="error",
                latency_ms=latency_ms,
                error=str(exc),
                transport="http",
            )
            raise McpServerUnavailable(
                f"HTTP error calling '{server_key}': {exc}",
                server_key=server_key,
                tool_name=tool_name,
                transport="http",
                latency_ms=latency_ms,
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000

        if "error" in body:
            error = body["error"] or {}
            error_msg = str(error.get("message") or "MCP HTTP request failed")
            self._trace(
                run_id=run_id,
                mode=mode,
                step=step,
                agent_name=agent_name,
                event_type="mcp_call_failed",
                server_key=server_key,
                tool_name=tool_name,
                status="error",
                severity="error",
                latency_ms=latency_ms,
                error=error_msg,
                transport="http",
            )
            raise McpServerUnavailable(
                error_msg,
                server_key=server_key,
                tool_name=tool_name,
                transport="http",
                error_code=str(error.get("code") or ""),
                latency_ms=latency_ms,
            )

        tool_result = body.get("result") or {}
        structured = tool_result.get("structuredContent")
        if not isinstance(structured, dict):
            structured = {}
        message = _message_text(tool_result) or tool_name
        is_error = bool(tool_result.get("isError"))

        if is_error:
            error_code = None
            if isinstance(structured.get("error"), dict):
                error_code = str(structured["error"].get("code") or "").strip() or None
            self._trace(
                run_id=run_id,
                mode=mode,
                step=step,
                agent_name=agent_name,
                event_type="mcp_call_failed",
                server_key=server_key,
                tool_name=tool_name,
                status="error",
                severity="error",
                latency_ms=latency_ms,
                error=message,
                transport="http",
            )
            raise McpCallError(
                message,
                server_key=server_key,
                tool_name=tool_name,
                transport="http",
                latency_ms=latency_ms,
                structured_content=structured,
                error_code=error_code,
            )

        self._trace(
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
            event_type="mcp_call_completed",
            server_key=server_key,
            tool_name=tool_name,
            status="ok",
            latency_ms=latency_ms,
            content_excerpt=message,
            transport="http",
        )
        return McpToolResult(
            server_key=server_key,
            tool_name=tool_name,
            structured_content=structured,
            message=message,
            protocol_version=None,
            server_name=None,
            is_error=False,
            latency_ms=latency_ms,
            transport="http",
        )

    async def describe_server(
        self,
        server_key: str,
        *,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        server = self._server(server_key)
        command, cwd = self._server_command(server)
        env = os.environ.copy()
        env["MASCARADE_DIR"] = str(self.mascarade_dir)
        env["MASCARADE_ENV_FILE"] = str(self.mascarade_env_file)
        env["KILL_LIFE_ROOT"] = str(self.kill_life_root)
        env["AGENT_FACTORY_COCKPIT_DIR"] = str(self.agent_factory_cockpit_dir)
        timeout = timeout_s or server.timeout_s
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(cwd),
        )

        async def _request(message: dict[str, Any]) -> dict[str, Any]:
            if proc.stdin is None or proc.stdout is None:
                raise McpServerUnavailable(
                    f"MCP server '{server_key}' stdin/stdout unavailable",
                    server_key=server_key,
                    transport=server.transport,
                )
            await _write_message(proc.stdin, message)
            response = await asyncio.wait_for(_read_message(proc.stdout), timeout=timeout)
            if response is None:
                raise McpServerUnavailable(
                    f"MCP server '{server_key}' returned EOF",
                    server_key=server_key,
                    transport=server.transport,
                )
            if "error" in response:
                error = response["error"] or {}
                raise McpServerUnavailable(
                    str(error.get("message") or "MCP request failed"),
                    server_key=server_key,
                    transport=server.transport,
                    error_code=str(error.get("code") or ""),
                )
            return response

        try:
            initialize = await _request(
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
            )
            init_result = initialize.get("result") or {}
            protocol_version = str(init_result.get("protocolVersion") or "")
            server_info = init_result.get("serverInfo") or {}
            if proc.stdin is not None:
                await _write_message(
                    proc.stdin,
                    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                )
            tools = (
                await _request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            ).get("result", {})
            resources = (
                await _request(
                    {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}}
                )
            ).get("result", {})
            prompts = (
                await _request({"jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}})
            ).get("result", {})
            return {
                "ok": True,
                "server_key": server_key,
                "label": server.label or server_key,
                "description": server.description or "",
                "protocol_version": protocol_version,
                "server_info": server_info,
                "tool_count": len(
                    tools.get("tools", []) if isinstance(tools.get("tools", []), list) else []
                ),
                "resource_count": len(
                    resources.get("resources", [])
                    if isinstance(resources.get("resources", []), list)
                    else []
                ),
                "prompt_count": len(
                    prompts.get("prompts", [])
                    if isinstance(prompts.get("prompts", []), list)
                    else []
                ),
                "tools": tools.get("tools", []),
                "resources": resources.get("resources", []),
                "prompts": prompts.get("prompts", []),
            }
        finally:
            if proc.stdin is not None:
                proc.stdin.close()
                try:
                    await proc.stdin.wait_closed()
                except (OSError, RuntimeError):
                    pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except TimeoutError:
                proc.kill()
                await proc.wait()

    async def read_resource(
        self,
        server_key: str,
        uri: str,
        *,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        server = self._server(server_key)
        command, cwd = self._server_command(server)
        env = os.environ.copy()
        env["MASCARADE_DIR"] = str(self.mascarade_dir)
        env["MASCARADE_ENV_FILE"] = str(self.mascarade_env_file)
        env["KILL_LIFE_ROOT"] = str(self.kill_life_root)
        env["AGENT_FACTORY_COCKPIT_DIR"] = str(self.agent_factory_cockpit_dir)
        timeout = timeout_s or server.timeout_s
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(cwd),
        )

        async def _request(message: dict[str, Any]) -> dict[str, Any]:
            if proc.stdin is None or proc.stdout is None:
                raise McpServerUnavailable(
                    f"MCP server '{server_key}' stdin/stdout unavailable",
                    server_key=server_key,
                    transport=server.transport,
                )
            await _write_message(proc.stdin, message)
            response = await asyncio.wait_for(_read_message(proc.stdout), timeout=timeout)
            if response is None:
                raise McpServerUnavailable(
                    f"MCP server '{server_key}' returned EOF",
                    server_key=server_key,
                    transport=server.transport,
                )
            if "error" in response:
                error = response["error"] or {}
                raise McpServerUnavailable(
                    str(error.get("message") or "MCP request failed"),
                    server_key=server_key,
                    transport=server.transport,
                    error_code=str(error.get("code") or ""),
                )
            return response

        try:
            await _request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            if proc.stdin is not None:
                await _write_message(
                    proc.stdin,
                    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                )
            response = await _request(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "resources/read",
                    "params": {"uri": uri},
                }
            )
            result = response.get("result", {})
            contents = result.get("contents", []) if isinstance(result, dict) else []
            if not isinstance(contents, list) or not contents:
                return {"uri": uri, "payload": {}, "raw_text": ""}
            first = contents[0] if isinstance(contents[0], dict) else {}
            raw_text = str(first.get("text", "") or "")
            try:
                payload = json.loads(raw_text) if raw_text else {}
            except json.JSONDecodeError:
                payload = {}
            return {
                "uri": uri,
                "payload": payload if isinstance(payload, dict) else {},
                "raw_text": raw_text,
                "mime_type": str(first.get("mimeType", "") or ""),
            }
        finally:
            if proc.stdin is not None:
                proc.stdin.close()
                try:
                    await proc.stdin.wait_closed()
                except (OSError, RuntimeError):
                    pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except TimeoutError:
                proc.kill()
                await proc.wait()

    async def knowledge_base_search(
        self,
        query: str,
        *,
        limit: int = 10,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        if settings.knowledge_base_provider.strip().lower() == "kxkm":
            return await self.kxkm_rag_search(
                query,
                limit=limit,
                project_id=project_id,
                federation_scope=federation_scope,
                knowledge_scope=knowledge_scope,
                run_id=run_id,
                mode=mode,
                step=step,
                agent_name=agent_name,
            )
        result = await self.call_tool(
            "knowledge-base",
            "search_pages",
            {"query": query, "limit": limit},
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def kxkm_rag_search(
        self,
        query: str,
        *,
        limit: int = 10,
        project_id: str | None = None,
        federation_scope: list[str] | tuple[str, ...] | None = None,
        knowledge_scope: str = "project",
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        import httpx

        if not query.strip():
            return {
                "ok": True,
                "provider": "kxkm",
                "provider_label": "kxkm",
                "results": [],
                "total": 0,
            }

        normalized_project, normalized_federation, normalized_scope = _normalize_scope(
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )
        base_url = settings.kxkm_rag_url.strip().rstrip("/")
        if not base_url:
            raise McpServerUnavailable(
                "kxkm RAG URL is not configured",
                server_key="kxkm",
                tool_name="kxkm_rag_search",
                transport="http-rest",
                error_code="missing_base_url",
            )

        started = time.perf_counter()
        self._trace(
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
            event_type="mcp_call_started",
            server_key="kxkm",
            tool_name="kxkm_rag_search",
            status="started",
            transport="http-rest",
        )

        try:
            async with httpx.AsyncClient(timeout=settings.kxkm_timeout_seconds) as http:
                response = await http.post(
                    f"{base_url}/api/v2/rag/search",
                    headers={
                        "x-mascarade-project-id": normalized_project,
                        "x-mascarade-knowledge-scope": normalized_scope,
                        "x-mascarade-federation-scope": ",".join(normalized_federation),
                    },
                    json={
                        "query": query.strip(),
                        "limit": max(1, min(limit, 50)),
                        "project_id": normalized_project,
                        "federation_scope": normalized_federation,
                        "knowledge_scope": normalized_scope,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            self._trace(
                run_id=run_id,
                mode=mode,
                step=step,
                agent_name=agent_name,
                event_type="mcp_call_failed",
                server_key="kxkm",
                tool_name="kxkm_rag_search",
                status="timeout",
                severity="error",
                latency_ms=latency_ms,
                error="kxkm RAG timeout",
                transport="http-rest",
            )
            raise McpServerUnavailable(
                "kxkm RAG timeout",
                server_key="kxkm",
                tool_name="kxkm_rag_search",
                transport="http-rest",
                latency_ms=latency_ms,
                error_code="timeout",
            ) from exc
        except httpx.HTTPError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            self._trace(
                run_id=run_id,
                mode=mode,
                step=step,
                agent_name=agent_name,
                event_type="mcp_call_failed",
                server_key="kxkm",
                tool_name="kxkm_rag_search",
                status="error",
                severity="error",
                latency_ms=latency_ms,
                error=str(exc),
                transport="http-rest",
            )
            raise McpServerUnavailable(
                f"kxkm RAG HTTP error: {exc}",
                server_key="kxkm",
                tool_name="kxkm_rag_search",
                transport="http-rest",
                latency_ms=latency_ms,
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        raw_results = data.get("results") or []
        results: list[dict[str, Any]] = []
        for index, item in enumerate(raw_results[:limit]):
            if not isinstance(item, dict):
                item = {"text": str(item)}
            text = str(item.get("text") or item.get("content") or item.get("chunk") or "").strip()
            results.append(
                {
                    "id": str(item.get("id") or item.get("chunk_id") or f"kxkm-{index + 1}"),
                    "title": text.splitlines()[0][:140] if text else f"kxkm-{index + 1}",
                    "url": str(item.get("url") or item.get("source_url") or ""),
                    "provider": "kxkm",
                    "text": text,
                    "score": item.get("score"),
                    "metadata": {
                        "project_id": normalized_project,
                        "knowledge_scope": normalized_scope,
                        "federation_scope": normalized_federation,
                        **{
                            key: value
                            for key, value in item.items()
                            if key not in {"id", "chunk_id", "text", "content", "chunk", "url", "source_url", "score"}
                        },
                    },
                }
            )

        result_payload = {
            "ok": bool(payload.get("ok", True)) if isinstance(payload, dict) else True,
            "provider": "kxkm",
            "provider_label": "kxkm",
            "project_id": normalized_project,
            "knowledge_scope": normalized_scope,
            "federation_scope": normalized_federation,
            "results": results,
            "total": int(data.get("total", len(results))) if isinstance(data, dict) else len(results),
        }
        self._trace(
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
            event_type="mcp_call_completed",
            server_key="kxkm",
            tool_name="kxkm_rag_search",
            status="ok",
            latency_ms=latency_ms,
            content_excerpt=f"kxkm results={result_payload['total']}",
            transport="http-rest",
        )
        return result_payload

    async def knowledge_base_read_page(
        self,
        page_id: str,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "knowledge-base",
            "read_page",
            {"page_id": page_id},
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def knowledge_base_append(
        self,
        page_id: str,
        content: str,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "knowledge-base",
            "append_to_page",
            {"page_id": page_id, "content": content},
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def knowledge_base_create_page(
        self,
        parent_id: str,
        title: str,
        content: str = "",
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "knowledge-base",
            "create_page",
            {
                "parent_id": parent_id,
                "title": title,
                "content": content,
            },
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def github_list_allowlisted_workflows(
        self,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "github-dispatch",
            "list_allowlisted_workflows",
            {},
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def github_dispatch_workflow(
        self,
        workflow_file: str,
        *,
        ref: str | None = None,
        inputs: dict[str, Any] | None = None,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "github-dispatch",
            "dispatch_workflow",
            {
                "workflow_file": workflow_file,
                **({"ref": ref} if ref else {}),
                **({"inputs": inputs} if inputs else {}),
            },
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def github_get_dispatch_status(
        self,
        dispatch_id: str,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "github-dispatch",
            "get_dispatch_status",
            {"dispatch_id": dispatch_id},
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def freecad_get_runtime_info(
        self,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "freecad",
            "get_runtime_info",
            {},
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def freecad_create_document(
        self,
        output_path: str,
        *,
        name: str = "McpDocument",
        primitive: str = "box",
        length: float = 10.0,
        width: float = 8.0,
        height: float = 6.0,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "freecad",
            "create_document",
            {
                "output_path": output_path,
                "name": name,
                "primitive": primitive,
                "length": length,
                "width": width,
                "height": height,
            },
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def freecad_export_document(
        self,
        document_path: str,
        output_path: str,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "freecad",
            "export_document",
            {
                "document_path": document_path,
                "output_path": output_path,
            },
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def freecad_run_python_script(
        self,
        script: str,
        *,
        output_path: str | None = None,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        _validate_freecad_script(script)
        arguments: dict[str, Any] = {"script": script}
        if output_path:
            arguments["output_path"] = output_path
        result = await self.call_tool(
            "freecad",
            "run_python_script",
            arguments,
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def openscad_get_runtime_info(
        self,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "openscad",
            "get_runtime_info",
            {},
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def openscad_validate_model(
        self,
        source: str,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "openscad",
            "validate_model",
            {"source": source},
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def openscad_render_model(
        self,
        source: str,
        output_path: str,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "openscad",
            "render_model",
            {
                "source": source,
                "output_path": output_path,
            },
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def openscad_export_model(
        self,
        source: str,
        output_path: str,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "openscad",
            "export_model",
            {
                "source": source,
                "output_path": output_path,
            },
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    # ------------------------------------------------------------------
    # Graphiti Knowledge Graph convenience methods
    # ------------------------------------------------------------------

    async def graphiti_add_episode(
        self,
        content: str,
        source: str = "mascarade",
        *,
        source_description: str = "",
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "graphiti",
            "add_episode",
            {
                "content": content,
                "source": source,
                "source_description": source_description,
            },
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def graphiti_search(
        self,
        query: str,
        *,
        limit: int = 10,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "graphiti",
            "search",
            {"query": query, "limit": limit},
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content

    async def graphiti_get_entity(
        self,
        name: str,
        *,
        run_id: str | None = None,
        mode: str = "internal",
        step: int = 0,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        result = await self.call_tool(
            "graphiti",
            "get_entity",
            {"name": name},
            run_id=run_id,
            mode=mode,
            step=step,
            agent_name=agent_name,
        )
        return result.structured_content
