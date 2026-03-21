"""MCP Server — expose mascarade agents as MCP tools via stdio.

Implements the Model Context Protocol (2025-06-18) over JSON-RPC 2.0 on
stdin/stdout so that external clients (Claude Code, Cursor, etc.) can
discover and invoke mascarade agents without any additional SDK dependency.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import traceback
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from mascarade.agents.registry import AgentRegistry
    from mascarade.mcp.client import McpRuntimeClient
    from mascarade.orchestrator.engine import Orchestrator
    from mascarade.router.router import Router

logger = logging.getLogger("mascarade.mcp.server")

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "mascarade"
SERVER_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Tool definitions — exposed to MCP clients via tools/list
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_agents",
        "description": (
            "List all available mascarade agents with their descriptions, "
            "preferred providers, and configuration."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "run_agent",
        "description": (
            "Execute a mascarade agent with a prompt and return the LLM response. "
            "Supports optional provider, model, and temperature overrides."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent to execute.",
                },
                "prompt": {
                    "type": "string",
                    "description": "The user prompt to send to the agent.",
                },
                "provider": {
                    "type": "string",
                    "description": "LLM provider override (e.g. 'claude', 'openai').",
                },
                "model": {
                    "type": "string",
                    "description": "Model override (e.g. 'claude-sonnet-4-20250514').",
                },
                "temperature": {
                    "type": "number",
                    "description": "Sampling temperature override (0.0 – 2.0).",
                },
            },
            "required": ["agent_name", "prompt"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the mascarade knowledge base (Memos / Docmost / kxkm RAG) "
            "and return matching entries."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text search query.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 10, max 50).",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_providers",
        "description": (
            "Return the list of registered LLM providers with availability status."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "orchestrate",
        "description": (
            "Run a multi-agent orchestration pipeline. Agents are executed "
            "according to the chosen mode: sequential (chain), parallel "
            "(fan-out), or pipeline (streaming handoff)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered list of agent names to involve.",
                },
                "prompt": {
                    "type": "string",
                    "description": "The prompt shared across agents.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["sequential", "parallel", "pipeline"],
                    "description": "Execution mode (default: sequential).",
                },
            },
            "required": ["agent_names", "prompt"],
            "additionalProperties": False,
        },
    },
]

_TOOL_NAMES = {t["name"] for t in TOOLS}


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def _jsonrpc_response(id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _jsonrpc_error(
    id: Any,
    code: int,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": err}


# Standard JSON-RPC error codes
_PARSE_ERROR = -32700
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603


# ---------------------------------------------------------------------------
# MCP tool result helpers
# ---------------------------------------------------------------------------

def _tool_result_text(text: str, *, is_error: bool = False) -> dict[str, Any]:
    """Build an MCP tools/call result payload with a single text content block."""
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


def _tool_result_json(obj: Any, *, is_error: bool = False) -> dict[str, Any]:
    """Build an MCP tools/call result with a JSON-serialised text block."""
    return _tool_result_text(
        json.dumps(obj, ensure_ascii=False, indent=2),
        is_error=is_error,
    )


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class McpServer:
    """Stdio-based MCP server exposing mascarade capabilities.

    The server reads newline-delimited JSON-RPC 2.0 messages from stdin and
    writes responses to stdout, following the MCP specification.
    """

    def __init__(
        self,
        router: Router,
        registry: AgentRegistry,
        orchestrator: Orchestrator | None = None,
        mcp_client: McpRuntimeClient | None = None,
    ) -> None:
        self.router = router
        self.registry = registry
        self.orchestrator = orchestrator
        self.mcp_client = mcp_client

        self._initialized = False

        self._handlers: dict[str, Any] = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized_notification,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "ping": self._handle_ping,
        }

        self._tool_dispatch: dict[str, Any] = {
            "list_agents": self._tool_list_agents,
            "run_agent": self._tool_run_agent,
            "search_knowledge_base": self._tool_search_knowledge_base,
            "list_providers": self._tool_list_providers,
            "orchestrate": self._tool_orchestrate,
        }

    # ------------------------------------------------------------------
    # Protocol handlers
    # ------------------------------------------------------------------

    async def _handle_initialize(
        self, params: dict[str, Any],
    ) -> dict[str, Any]:
        """Respond to the MCP initialize handshake."""
        self._initialized = True
        client_info = params.get("clientInfo", {})
        logger.info(
            "MCP initialize from client=%s version=%s",
            client_info.get("name", "unknown"),
            client_info.get("version", "unknown"),
        )
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        }

    async def _handle_initialized_notification(
        self, params: dict[str, Any],
    ) -> None:
        """Handle the 'initialized' notification (no response expected)."""
        logger.info("MCP client confirmed initialization")
        return None

    async def _handle_ping(
        self, params: dict[str, Any],
    ) -> dict[str, Any]:
        return {}

    async def _handle_tools_list(
        self, params: dict[str, Any],
    ) -> dict[str, Any]:
        return {"tools": TOOLS}

    async def _handle_tools_call(
        self, params: dict[str, Any],
    ) -> dict[str, Any]:
        tool_name = params.get("name", "")
        arguments = params.get("arguments") or {}

        handler = self._tool_dispatch.get(tool_name)
        if handler is None:
            return _tool_result_text(
                f"Unknown tool: {tool_name}. "
                f"Available: {', '.join(sorted(_TOOL_NAMES))}",
                is_error=True,
            )

        try:
            return await handler(arguments)
        except Exception as exc:
            logger.exception("Tool %s failed", tool_name)
            return _tool_result_text(
                f"Tool execution error ({type(exc).__name__}): {exc}",
                is_error=True,
            )

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _tool_list_agents(
        self, arguments: dict[str, Any],
    ) -> dict[str, Any]:
        agents = self.registry.list()
        result = [
            {
                "name": a.name,
                "description": a.description,
                "preferred_provider": a.preferred_provider,
                "preferred_model": a.preferred_model,
                "strategy": str(a.strategy),
                "temperature": a.temperature,
                "tools": a.tools,
                "builtin": self.registry.is_builtin(a.name),
            }
            for a in agents
        ]
        return _tool_result_json(result)

    async def _tool_run_agent(
        self, arguments: dict[str, Any],
    ) -> dict[str, Any]:
        agent_name = arguments.get("agent_name", "").strip()
        prompt = arguments.get("prompt", "").strip()

        if not agent_name:
            return _tool_result_text(
                "Missing required parameter: agent_name", is_error=True,
            )
        if not prompt:
            return _tool_result_text(
                "Missing required parameter: prompt", is_error=True,
            )

        try:
            agent = self.registry.get(agent_name)
        except KeyError as exc:
            return _tool_result_text(str(exc), is_error=True)

        # Build overrides from optional params
        provider = arguments.get("provider") or agent.preferred_provider
        model = arguments.get("model") or agent.preferred_model
        temperature = arguments.get("temperature", agent.temperature)

        try:
            temperature = float(temperature)
            temperature = max(0.0, min(temperature, 2.0))
        except (TypeError, ValueError):
            temperature = agent.temperature

        messages = [{"role": "user", "content": prompt}]

        response = await self.router.send(
            messages,
            strategy=agent.strategy,
            provider=provider,
            model=model,
            system=agent.system_prompt,
            temperature=temperature,
            max_tokens=agent.max_tokens,
        )

        return _tool_result_json({
            "agent": agent_name,
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": dict(response.usage) if response.usage else None,
        })

    async def _tool_search_knowledge_base(
        self, arguments: dict[str, Any],
    ) -> dict[str, Any]:
        query = arguments.get("query", "").strip()
        if not query:
            return _tool_result_text(
                "Missing required parameter: query", is_error=True,
            )

        limit = arguments.get("limit", 10)
        try:
            limit = max(1, min(int(limit), 50))
        except (TypeError, ValueError):
            limit = 10

        # Lazy import to avoid hard dependency at module level
        from mascarade.integrations.knowledge_base import KnowledgeBaseClient

        kb = KnowledgeBaseClient()
        try:
            results = await kb.search(query, limit=limit)
        finally:
            await kb.close()

        return _tool_result_json({
            "query": query,
            "count": len(results),
            "results": results,
        })

    async def _tool_list_providers(
        self, arguments: dict[str, Any],
    ) -> dict[str, Any]:
        providers = []
        for name, provider in self.router._providers.items():
            entry: dict[str, Any] = {
                "name": name,
                "available": provider.is_available(),
            }
            # Include models when the provider supports listing them
            if hasattr(provider, "models"):
                try:
                    entry["models"] = provider.models()
                except Exception:
                    entry["models"] = []
            providers.append(entry)

        return _tool_result_json(providers)

    async def _tool_orchestrate(
        self, arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if self.orchestrator is None:
            return _tool_result_text(
                "Orchestrator not available on this server instance.",
                is_error=True,
            )

        agent_names = arguments.get("agent_names")
        prompt = arguments.get("prompt", "").strip()
        mode = arguments.get("mode", "sequential").strip().lower()

        if not agent_names or not isinstance(agent_names, list):
            return _tool_result_text(
                "Missing or invalid required parameter: agent_names (must be a list)",
                is_error=True,
            )
        if not prompt:
            return _tool_result_text(
                "Missing required parameter: prompt", is_error=True,
            )

        # Validate all agent names before starting
        for name in agent_names:
            if name not in self.registry:
                available = [a.name for a in self.registry.list()]
                return _tool_result_text(
                    f"Agent '{name}' not found. Available: {available}",
                    is_error=True,
                )

        run = await self.orchestrator.run(
            agent_names=agent_names,
            prompt=prompt,
            mode=mode,
        )

        results = []
        for tr in run.results:
            results.append({
                "agent": tr.agent_name,
                "step": tr.step,
                "content": tr.response.content if tr.response else None,
                "model": tr.response.model if tr.response else None,
                "provider": tr.response.provider if tr.response else None,
                "error": tr.error,
            })

        return _tool_result_json({
            "run_id": run.run_id,
            "mode": str(run.mode),
            "results": results,
        })

    # ------------------------------------------------------------------
    # Stdio transport
    # ------------------------------------------------------------------

    async def run_stdio(self) -> None:
        """Main loop: read JSON-RPC from stdin, write responses to stdout.

        Messages are newline-delimited JSON. Each request is a JSON-RPC 2.0
        object. Notifications (no ``id``) receive no reply.
        """
        logger.info("mascarade MCP server starting on stdio")

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(
            lambda: protocol, sys.stdin,
        )

        # Wrap stdout for async writes
        transport, _ = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.BaseProtocol, sys.stdout,
        )

        try:
            while True:
                line = await reader.readline()
                if not line:
                    logger.info("stdin closed — shutting down")
                    break

                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                response = await self._process_message(line_str)
                if response is not None:
                    out = json.dumps(response, ensure_ascii=False) + "\n"
                    transport.write(out.encode("utf-8"))
        except asyncio.CancelledError:
            logger.info("MCP server cancelled")
        except Exception:
            logger.exception("Fatal error in MCP stdio loop")
        finally:
            transport.close()
            logger.info("mascarade MCP server stopped")

    async def _process_message(
        self, raw: str,
    ) -> dict[str, Any] | None:
        """Parse a single JSON-RPC message and dispatch to the handler."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Malformed JSON: %s", exc)
            return _jsonrpc_error(None, _PARSE_ERROR, f"Parse error: {exc}")

        if not isinstance(msg, dict):
            return _jsonrpc_error(
                None, _INVALID_REQUEST, "Request must be a JSON object",
            )

        method = msg.get("method", "")
        params = msg.get("params") or {}
        msg_id = msg.get("id")  # None for notifications

        handler = self._handlers.get(method)
        if handler is None:
            if msg_id is None:
                # Unknown notification — silently ignore per spec
                return None
            return _jsonrpc_error(
                msg_id,
                _METHOD_NOT_FOUND,
                f"Method not found: {method}",
            )

        try:
            result = await handler(params)
        except Exception as exc:
            logger.exception("Handler %s raised", method)
            if msg_id is None:
                return None
            return _jsonrpc_error(
                msg_id,
                _INTERNAL_ERROR,
                f"Internal error: {exc}",
                data=traceback.format_exc(),
            )

        # Notifications get no response
        if msg_id is None:
            return None

        return _jsonrpc_response(msg_id, result)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Launch the MCP server from the command line.

    Usage::

        python -m mascarade.mcp.server

    Or configure in your MCP client settings::

        {
            "mcpServers": {
                "mascarade": {
                    "command": "python",
                    "args": ["-m", "mascarade.mcp.server"]
                }
            }
        }
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        stream=sys.stderr,  # MCP protocol uses stdout; logs go to stderr
    )

    # Late imports to keep module-level lightweight
    from mascarade.agents.registry import AgentRegistry
    from mascarade.orchestrator.engine import Orchestrator
    from mascarade.router import Router

    router = Router()
    registry = AgentRegistry()

    # Auto-register builtin agents if the helper exists
    try:
        from mascarade.agents.builtins import register_builtins
        register_builtins(registry)
    except ImportError:
        logger.debug("No builtin agents module found — starting with empty registry")

    orchestrator = Orchestrator(router=router, registry=registry)

    server = McpServer(
        router=router,
        registry=registry,
        orchestrator=orchestrator,
    )

    logger.info(
        "Starting %s v%s (protocol %s)",
        SERVER_NAME,
        SERVER_VERSION,
        PROTOCOL_VERSION,
    )

    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
