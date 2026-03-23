"""Tests for the MCP server (JSON-RPC 2.0 over stdio)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

import pytest

from mascarade.mcp.server import (
    _TOOL_NAMES,
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    TOOLS,
    McpServer,
    _jsonrpc_error,
    _jsonrpc_response,
    _register_initial_agents,
    _tool_result_json,
    _tool_result_text,
)
from mascarade.router.providers.base import LLMResponse
from mascarade.router.router import Strategy

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeAgent:
    name: str
    description: str = "A test agent"
    system_prompt: str = "You are a test agent"
    preferred_provider: str | None = None
    preferred_model: str | None = None
    strategy: Strategy = Strategy.BEST
    routing_policy: str = "auto"
    tools: list[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096


class FakeRegistry:
    """Minimal agent registry for testing."""

    def __init__(self, agents: list[FakeAgent] | None = None):
        self._agents = {a.name: a for a in (agents or [])}
        self._builtins: set[str] = set()

    def list(self):
        return list(self._agents.values())

    def get(self, name: str):
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' not found")
        return self._agents[name]

    def is_builtin(self, name: str) -> bool:
        return name in self._builtins

    def __contains__(self, name: str) -> bool:
        return name in self._agents


class FakeRouter:
    """Minimal router for testing."""

    def __init__(self, response: LLMResponse | None = None):
        self._response = response or LLMResponse(
            content="Test MCP response",
            model="gpt-4",
            provider="openai",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        self.calls: list[dict] = []
        self._providers: dict = {}

    async def send(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return self._response


@pytest.fixture
def agents():
    return [
        FakeAgent(name="coder", description="Writes code"),
        FakeAgent(
            name="reviewer", description="Reviews code", preferred_provider="anthropic"
        ),
    ]


@pytest.fixture
def server(agents):
    registry = FakeRegistry(agents)
    router = FakeRouter()
    return McpServer(router=router, registry=registry)


@pytest.fixture
def server_with_orchestrator(agents):
    registry = FakeRegistry(agents)
    router = FakeRouter()
    orchestrator = AsyncMock()
    return McpServer(router=router, registry=registry, orchestrator=orchestrator)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


def test_jsonrpc_response_format():
    """Test JSON-RPC response has correct structure."""
    resp = _jsonrpc_response(1, {"tools": []})
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"] == {"tools": []}


def test_jsonrpc_error_format():
    """Test JSON-RPC error has correct structure."""
    err = _jsonrpc_error(2, -32600, "Invalid request")
    assert err["jsonrpc"] == "2.0"
    assert err["id"] == 2
    assert err["error"]["code"] == -32600
    assert err["error"]["message"] == "Invalid request"


def test_jsonrpc_error_with_data():
    """Test JSON-RPC error includes optional data field."""
    err = _jsonrpc_error(3, -32603, "Internal error", data="stack trace")
    assert err["error"]["data"] == "stack trace"


def test_tool_result_text():
    """Test MCP tool result with text content."""
    result = _tool_result_text("hello world")
    assert result["content"][0]["type"] == "text"
    assert result["content"][0]["text"] == "hello world"
    assert result["isError"] is False


def test_tool_result_text_error():
    """Test MCP tool result with error flag."""
    result = _tool_result_text("something failed", is_error=True)
    assert result["isError"] is True


def test_tool_result_json():
    """Test MCP tool result with JSON payload."""
    result = _tool_result_json({"key": "value"})
    content_text = result["content"][0]["text"]
    parsed = json.loads(content_text)
    assert parsed["key"] == "value"


# ---------------------------------------------------------------------------
# McpServer initialization tests
# ---------------------------------------------------------------------------


def test_server_initialization(server):
    """Test McpServer initializes with correct handlers."""
    assert not server._initialized
    assert "initialize" in server._handlers
    assert "tools/list" in server._handlers
    assert "tools/call" in server._handlers
    assert "ping" in server._handlers


def test_server_tool_dispatch(server):
    """Test all 5 tools are registered in dispatch table."""
    assert len(server._tool_dispatch) == 5
    assert "list_agents" in server._tool_dispatch
    assert "run_agent" in server._tool_dispatch
    assert "search_knowledge_base" in server._tool_dispatch
    assert "list_providers" in server._tool_dispatch
    assert "orchestrate" in server._tool_dispatch


def test_register_initial_agents_uses_default_registration():
    """The MCP bootstrap should register the default built-in agents."""
    registry = FakeRegistry()

    def fake_register_defaults(target_registry):
        target_registry._agents["coder"] = FakeAgent(name="coder")
        target_registry._builtins.add("coder")

    count = _register_initial_agents(registry, register_defaults=fake_register_defaults)

    assert count == 1
    assert "coder" in registry
    assert registry.is_builtin("coder") is True


# ---------------------------------------------------------------------------
# Protocol handler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_initialize(server):
    """Test MCP initialize handshake response."""
    result = await server._handle_initialize(
        {
            "protocolVersion": "2025-06-18",
            "clientInfo": {"name": "test-client", "version": "1.0"},
        }
    )

    assert server._initialized is True
    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert result["serverInfo"]["name"] == SERVER_NAME
    assert result["serverInfo"]["version"] == SERVER_VERSION
    assert "tools" in result["capabilities"]


@pytest.mark.asyncio
async def test_handle_initialized_notification(server):
    """Test initialized notification returns None."""
    result = await server._handle_initialized_notification({})
    assert result is None


@pytest.mark.asyncio
async def test_handle_ping(server):
    """Test ping handler returns empty dict."""
    result = await server._handle_ping({})
    assert result == {}


@pytest.mark.asyncio
async def test_handle_tools_list(server):
    """Test tools/list returns all 5 tools."""
    result = await server._handle_tools_list({})
    assert "tools" in result
    assert len(result["tools"]) == 5
    tool_names = {t["name"] for t in result["tools"]}
    assert tool_names == _TOOL_NAMES


@pytest.mark.asyncio
async def test_tools_list_has_input_schemas(server):
    """Test each tool in tools/list has a valid inputSchema."""
    result = await server._handle_tools_list({})
    for tool in result["tools"]:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"


# ---------------------------------------------------------------------------
# Tool execution tests: list_agents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_list_agents(server):
    """Test list_agents returns all registered agents."""
    result = await server._tool_list_agents({})
    content = json.loads(result["content"][0]["text"])
    assert len(content) == 2
    names = {a["name"] for a in content}
    assert names == {"coder", "reviewer"}


@pytest.mark.asyncio
async def test_tool_list_agents_includes_metadata(server):
    """Test list_agents includes description and provider info."""
    result = await server._tool_list_agents({})
    content = json.loads(result["content"][0]["text"])
    reviewer = next(a for a in content if a["name"] == "reviewer")
    assert reviewer["description"] == "Reviews code"
    assert reviewer["preferred_provider"] == "anthropic"


# ---------------------------------------------------------------------------
# Tool execution tests: run_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_run_agent(server):
    """Test run_agent executes agent and returns response."""
    result = await server._tool_run_agent(
        {
            "agent_name": "coder",
            "prompt": "Write a hello world",
        }
    )
    assert result["isError"] is False
    content = json.loads(result["content"][0]["text"])
    assert content["agent"] == "coder"
    assert content["content"] == "Test MCP response"
    assert content["model"] == "gpt-4"
    assert content["provider"] == "openai"


@pytest.mark.asyncio
async def test_tool_run_agent_missing_agent_name(server):
    """Test run_agent rejects missing agent_name."""
    result = await server._tool_run_agent({"prompt": "test"})
    assert result["isError"] is True
    assert "agent_name" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_tool_run_agent_missing_prompt(server):
    """Test run_agent rejects missing prompt."""
    result = await server._tool_run_agent({"agent_name": "coder"})
    assert result["isError"] is True
    assert "prompt" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_tool_run_agent_unknown_agent(server):
    """Test run_agent returns error for unknown agent."""
    result = await server._tool_run_agent(
        {
            "agent_name": "nonexistent",
            "prompt": "test",
        }
    )
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_tool_run_agent_with_overrides(server):
    """Test run_agent passes provider/model/temperature overrides."""
    result = await server._tool_run_agent(
        {
            "agent_name": "coder",
            "prompt": "test",
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.2,
        }
    )
    assert result["isError"] is False
    # Verify overrides were passed to router
    call = server.router.calls[0]
    assert call["provider"] == "anthropic"
    assert call["model"] == "claude-sonnet-4-20250514"
    assert call["temperature"] == 0.2


@pytest.mark.asyncio
async def test_tool_run_agent_invalid_temperature(server):
    """Test run_agent handles invalid temperature gracefully."""
    result = await server._tool_run_agent(
        {
            "agent_name": "coder",
            "prompt": "test",
            "temperature": "not_a_number",
        }
    )
    # Should fall back to agent default, not error
    assert result["isError"] is False
    call = server.router.calls[0]
    assert call["temperature"] == 0.7  # agent default


@pytest.mark.asyncio
async def test_tool_run_agent_temperature_clamped(server):
    """Test run_agent clamps temperature to 0.0-2.0 range."""
    result = await server._tool_run_agent(
        {
            "agent_name": "coder",
            "prompt": "test",
            "temperature": 5.0,
        }
    )
    assert result["isError"] is False
    call = server.router.calls[0]
    assert call["temperature"] == 2.0


# ---------------------------------------------------------------------------
# Tool execution tests: list_providers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_list_providers_empty(server):
    """Test list_providers with no providers registered."""
    result = await server._tool_list_providers({})
    content = json.loads(result["content"][0]["text"])
    assert content == []


@pytest.mark.asyncio
async def test_tool_list_providers_with_providers():
    """Test list_providers returns provider details."""

    class FakeProvider:
        def is_available(self):
            return True

        def models(self):
            return ["gpt-4", "gpt-3.5"]

    router = FakeRouter()
    router._providers = {"openai": FakeProvider()}
    registry = FakeRegistry()
    srv = McpServer(router=router, registry=registry)

    result = await srv._tool_list_providers({})
    content = json.loads(result["content"][0]["text"])
    assert len(content) == 1
    assert content[0]["name"] == "openai"
    assert content[0]["available"] is True
    assert content[0]["models"] == ["gpt-4", "gpt-3.5"]


# ---------------------------------------------------------------------------
# Tool execution tests: orchestrate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_orchestrate_no_orchestrator(server):
    """Test orchestrate returns error when orchestrator is not available."""
    result = await server._tool_orchestrate(
        {
            "agent_names": ["coder"],
            "prompt": "test",
        }
    )
    assert result["isError"] is True
    assert "not available" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_tool_orchestrate_missing_agent_names(server_with_orchestrator):
    """Test orchestrate rejects missing agent_names."""
    result = await server_with_orchestrator._tool_orchestrate(
        {
            "prompt": "test",
        }
    )
    assert result["isError"] is True
    assert "agent_names" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_tool_orchestrate_missing_prompt(server_with_orchestrator):
    """Test orchestrate rejects missing prompt."""
    result = await server_with_orchestrator._tool_orchestrate(
        {
            "agent_names": ["coder"],
        }
    )
    assert result["isError"] is True
    assert "prompt" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_tool_orchestrate_unknown_agent(server_with_orchestrator):
    """Test orchestrate rejects unknown agent name."""
    result = await server_with_orchestrator._tool_orchestrate(
        {
            "agent_names": ["nonexistent"],
            "prompt": "test",
        }
    )
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"]


# ---------------------------------------------------------------------------
# tools/call dispatch tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tools_call_unknown_tool(server):
    """Test tools/call with unknown tool name returns error."""
    result = await server._handle_tools_call(
        {
            "name": "unknown_tool",
            "arguments": {},
        }
    )
    assert result["isError"] is True
    assert "Unknown tool" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_tools_call_dispatches_correctly(server):
    """Test tools/call dispatches to correct tool handler."""
    result = await server._handle_tools_call(
        {
            "name": "list_agents",
            "arguments": {},
        }
    )
    assert result["isError"] is False
    content = json.loads(result["content"][0]["text"])
    assert len(content) == 2


@pytest.mark.asyncio
async def test_tools_call_handles_tool_exception(server):
    """Test tools/call catches exceptions from tool handlers."""
    # Force an exception in list_providers by making _providers raise
    server.router._providers = MagicMock(side_effect=RuntimeError("broken"))
    # items() will raise
    server.router._providers.items.side_effect = RuntimeError("broken")

    result = await server._handle_tools_call(
        {
            "name": "list_providers",
            "arguments": {},
        }
    )
    assert result["isError"] is True
    assert "Tool execution error" in result["content"][0]["text"]


# ---------------------------------------------------------------------------
# _process_message tests (JSON-RPC dispatch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_message_valid_request(server):
    """Test processing a valid JSON-RPC request."""
    raw = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "ping",
            "params": {},
        }
    )
    response = await server._process_message(raw)
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"] == {}


@pytest.mark.asyncio
async def test_process_message_malformed_json(server):
    """Test processing malformed JSON returns parse error."""
    response = await server._process_message("{invalid json")
    assert response["error"]["code"] == -32700


@pytest.mark.asyncio
async def test_process_message_not_object(server):
    """Test processing non-object JSON returns invalid request."""
    response = await server._process_message('"just a string"')
    assert response["error"]["code"] == -32600


@pytest.mark.asyncio
async def test_process_message_unknown_method(server):
    """Test processing unknown method returns method not found."""
    raw = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "nonexistent/method",
            "params": {},
        }
    )
    response = await server._process_message(raw)
    assert response["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_process_message_notification_no_response(server):
    """Test notifications (no id) get no response."""
    raw = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {},
        }
    )
    response = await server._process_message(raw)
    assert response is None


@pytest.mark.asyncio
async def test_process_message_unknown_notification_ignored(server):
    """Test unknown notification is silently ignored."""
    raw = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "unknown/notification",
            "params": {},
        }
    )
    response = await server._process_message(raw)
    assert response is None


# ---------------------------------------------------------------------------
# Constants / metadata tests
# ---------------------------------------------------------------------------


def test_tools_constant_has_five_tools():
    """Test TOOLS constant defines exactly 5 tools."""
    assert len(TOOLS) == 5


def test_tool_names_set_matches_tools():
    """Test _TOOL_NAMES matches TOOLS definitions."""
    assert _TOOL_NAMES == {t["name"] for t in TOOLS}


def test_protocol_version_format():
    """Test protocol version is a valid date string."""
    assert PROTOCOL_VERSION == "2025-06-18"
