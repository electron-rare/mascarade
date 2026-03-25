from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mascarade.config import settings
from mascarade.mcp import McpCallError, McpRuntimeClient, McpServerUnavailable
from mascarade.observability import AgentTraceBuffer


@pytest.mark.asyncio
async def test_stdio_mcp_client_calls_fake_server(tmp_path: Path):
    server_script = tmp_path / "fake_mcp.py"
    server_script.write_text(
        """
import json
import sys

def read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\\r\\n", b"\\n"):
            break
        key, _, value = line.decode("utf-8").partition(":")
        headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0") or "0")
    if length <= 0:
        return None
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))

def write_message(payload):
    body = json.dumps(payload).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\\r\\n\\r\\n".encode("utf-8"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()

while True:
    request = read_message()
    if request is None:
        break
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        write_message({"jsonrpc":"2.0","id":request_id,"result":{"protocolVersion":"2025-03-26","serverInfo":{"name":"fake"}}})
    elif method == "notifications/initialized":
        continue
    elif method == "tools/call":
        args = (request.get("params") or {}).get("arguments") or {}
        write_message({"jsonrpc":"2.0","id":request_id,"result":{"content":[{"type":"text","text":"ok"}],"structuredContent":{"ok":True,"echo":args},"isError":False}})
    else:
        write_message({"jsonrpc":"2.0","id":request_id,"error":{"code":-32601,"message":"unknown"}})
""",
        encoding="utf-8",
    )
    launcher = tmp_path / "run_fake_mcp.sh"
    launcher.write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\nexec python3 "$(dirname "$0")/fake_mcp.py"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)

    trace_buffer = AgentTraceBuffer()
    client = McpRuntimeClient(trace_buffer=trace_buffer)
    client._servers["fake"] = client._server("knowledge-base").__class__(  # type: ignore[attr-defined]
        key="fake",
        launcher=launcher,
        timeout_s=5.0,
    )

    result = await client.call_tool(
        "fake",
        "echo",
        {"hello": "world"},
        run_id="run-mcp-1",
        mode="test",
        agent_name="tester",
    )

    assert result.server_name == "fake"
    assert result.protocol_version == "2025-03-26"
    assert result.structured_content["echo"] == {"hello": "world"}
    events = trace_buffer.run_events("run-mcp-1")
    assert [event.event_type for event in events][-2:] == [
        "mcp_call_started",
        "mcp_call_completed",
    ]
    assert events[-1].mcp_server == "fake"
    assert events[-1].mcp_tool == "echo"


@pytest.mark.asyncio
async def test_stdio_mcp_client_raises_for_tool_error(tmp_path: Path):
    server_script = tmp_path / "fake_error_mcp.py"
    server_script.write_text(
        """
import json
import sys

def read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\\r\\n", b"\\n"):
            break
        key, _, value = line.decode("utf-8").partition(":")
        headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0") or "0")
    if length <= 0:
        return None
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))

def write_message(payload):
    body = json.dumps(payload).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\\r\\n\\r\\n".encode("utf-8"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()

while True:
    request = read_message()
    if request is None:
        break
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        write_message({"jsonrpc":"2.0","id":request_id,"result":{"protocolVersion":"2025-03-26","serverInfo":{"name":"fake-error"}}})
    elif method == "notifications/initialized":
        continue
    elif method == "tools/call":
        write_message({"jsonrpc":"2.0","id":request_id,"result":{"content":[{"type":"text","text":"missing secret"}],"structuredContent":{"ok":False,"error":{"code":"missing_secret","message":"missing secret"}},"isError":True}})
    else:
        write_message({"jsonrpc":"2.0","id":request_id,"error":{"code":-32601,"message":"unknown"}})
""",
        encoding="utf-8",
    )
    launcher = tmp_path / "run_fake_error_mcp.sh"
    launcher.write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\nexec python3 "$(dirname "$0")/fake_error_mcp.py"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)

    client = McpRuntimeClient()
    client._servers["fake-error"] = client._server("knowledge-base").__class__(  # type: ignore[attr-defined]
        key="fake-error",
        launcher=launcher,
        timeout_s=5.0,
    )

    with pytest.raises(McpCallError) as exc_info:
        await client.call_tool("fake-error", "boom", {})

    assert exc_info.value.error_code == "missing_secret"
    assert exc_info.value.structured_content["error"]["message"] == "missing secret"


# ------------------------------------------------------------------
# Graphiti / HTTP transport tests
# ------------------------------------------------------------------


def test_graphiti_server_registered_when_enabled():
    with patch.dict(os.environ, {"GRAPHITI_ENABLED": "true"}):
        client = McpRuntimeClient()
    assert "graphiti" in client._servers
    srv = client._servers["graphiti"]
    assert srv.transport == "http"
    assert srv.url == "http://mascarade-graphiti-mcp:8000"
    assert srv.label == "Graphiti Knowledge Graph"


def test_graphiti_server_not_registered_when_disabled():
    with patch.dict(os.environ, {"GRAPHITI_ENABLED": "false"}):
        client = McpRuntimeClient()
    assert "graphiti" not in client._servers


def test_graphiti_server_custom_url():
    with patch.dict(
        os.environ,
        {"GRAPHITI_ENABLED": "true", "GRAPHITI_MCP_URL": "http://custom:9999"},
    ):
        client = McpRuntimeClient()
    assert client._servers["graphiti"].url == "http://custom:9999"


def test_graphiti_visible_in_list_servers():
    with patch.dict(os.environ, {"GRAPHITI_ENABLED": "true"}):
        client = McpRuntimeClient()
    keys = [s["key"] for s in client.list_servers()]
    assert "graphiti" in keys


class _FakeResponse:
    """Minimal stand-in for httpx.Response."""

    def __init__(self, json_body: dict, status_code: int = 200):
        self._json = json_body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                "error", request=None, response=self  # type: ignore[arg-type]
            )

    def json(self) -> dict:
        return self._json


@pytest.fixture(autouse=True)
def restore_kxkm_settings():
    snapshot = {
        "knowledge_base_provider": settings.knowledge_base_provider,
        "mascarade_project_id": settings.mascarade_project_id,
        "kxkm_rag_url": settings.kxkm_rag_url,
        "kxkm_timeout_seconds": settings.kxkm_timeout_seconds,
    }
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


@pytest.mark.asyncio
async def test_call_tool_http_success():
    with patch.dict(os.environ, {"GRAPHITI_ENABLED": "true"}):
        client = McpRuntimeClient(trace_buffer=AgentTraceBuffer())

    response_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [{"type": "text", "text": "found 3 results"}],
            "structuredContent": {"results": [1, 2, 3]},
            "isError": False,
        },
    }

    mock_post = AsyncMock(return_value=_FakeResponse(response_body))
    with patch("httpx.AsyncClient") as mock_client_cls:
        ctx = AsyncMock()
        ctx.post = mock_post
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = ctx

        result = await client.call_tool_http(
            "graphiti", "search", {"query": "test"}, run_id="r1"
        )

    assert result.server_key == "graphiti"
    assert result.tool_name == "search"
    assert result.transport == "http"
    assert result.structured_content == {"results": [1, 2, 3]}
    assert result.message == "found 3 results"
    assert not result.is_error


@pytest.mark.asyncio
async def test_call_tool_http_error_response():
    with patch.dict(os.environ, {"GRAPHITI_ENABLED": "true"}):
        client = McpRuntimeClient()

    response_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32600, "message": "invalid request"},
    }

    mock_post = AsyncMock(return_value=_FakeResponse(response_body))
    with patch("httpx.AsyncClient") as mock_client_cls:
        ctx = AsyncMock()
        ctx.post = mock_post
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = ctx

        with pytest.raises(McpServerUnavailable, match="invalid request"):
            await client.call_tool_http("graphiti", "bad_tool", {})


@pytest.mark.asyncio
async def test_call_tool_http_tool_error():
    with patch.dict(os.environ, {"GRAPHITI_ENABLED": "true"}):
        client = McpRuntimeClient()

    response_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [{"type": "text", "text": "entity not found"}],
            "structuredContent": {
                "ok": False,
                "error": {"code": "not_found", "message": "entity not found"},
            },
            "isError": True,
        },
    }

    mock_post = AsyncMock(return_value=_FakeResponse(response_body))
    with patch("httpx.AsyncClient") as mock_client_cls:
        ctx = AsyncMock()
        ctx.post = mock_post
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = ctx

        with pytest.raises(McpCallError) as exc_info:
            await client.call_tool_http("graphiti", "get_entity", {"name": "x"})

    assert exc_info.value.error_code == "not_found"
    assert exc_info.value.transport == "http"


@pytest.mark.asyncio
async def test_call_tool_dispatches_to_http():
    """call_tool() should auto-dispatch to call_tool_http() for HTTP servers."""
    with patch.dict(os.environ, {"GRAPHITI_ENABLED": "true"}):
        client = McpRuntimeClient()

    client.call_tool_http = AsyncMock(  # type: ignore[method-assign]
        return_value=McpRuntimeClient.__dict__  # placeholder, won't be inspected
    )
    # We just check that call_tool delegates — the AsyncMock prevents real HTTP calls.
    try:
        await client.call_tool("graphiti", "search", {"query": "hello"})
    except Exception:
        pass
    client.call_tool_http.assert_called_once()


@pytest.mark.asyncio
async def test_graphiti_search_convenience():
    with patch.dict(os.environ, {"GRAPHITI_ENABLED": "true"}):
        client = McpRuntimeClient()

    from mascarade.mcp.client import McpToolResult

    fake_result = McpToolResult(
        server_key="graphiti",
        tool_name="search",
        structured_content={"results": ["a", "b"]},
        message="ok",
        protocol_version=None,
        server_name=None,
        is_error=False,
        latency_ms=10.0,
        transport="http",
    )
    client.call_tool = AsyncMock(return_value=fake_result)  # type: ignore[method-assign]

    result = await client.graphiti_search("test query", limit=5, run_id="r2")
    assert result == {"results": ["a", "b"]}
    client.call_tool.assert_called_once_with(
        "graphiti",
        "search",
        {"query": "test query", "limit": 5},
        run_id="r2",
        mode="internal",
        step=0,
        agent_name=None,
    )


@pytest.mark.asyncio
async def test_graphiti_add_episode_convenience():
    with patch.dict(os.environ, {"GRAPHITI_ENABLED": "true"}):
        client = McpRuntimeClient()

    from mascarade.mcp.client import McpToolResult

    fake_result = McpToolResult(
        server_key="graphiti",
        tool_name="add_episode",
        structured_content={"ok": True},
        message="ok",
        protocol_version=None,
        server_name=None,
        is_error=False,
        latency_ms=10.0,
        transport="http",
    )
    client.call_tool = AsyncMock(return_value=fake_result)  # type: ignore[method-assign]

    result = await client.graphiti_add_episode("some content", "test-src")
    assert result == {"ok": True}
    call_args = client.call_tool.call_args
    assert call_args[0][0] == "graphiti"
    assert call_args[0][1] == "add_episode"
    assert call_args[0][2]["content"] == "some content"
    assert call_args[0][2]["source"] == "test-src"


@pytest.mark.asyncio
async def test_graphiti_get_entity_convenience():
    with patch.dict(os.environ, {"GRAPHITI_ENABLED": "true"}):
        client = McpRuntimeClient()

    from mascarade.mcp.client import McpToolResult

    fake_result = McpToolResult(
        server_key="graphiti",
        tool_name="get_entity",
        structured_content={"name": "Alice", "type": "person"},
        message="ok",
        protocol_version=None,
        server_name=None,
        is_error=False,
        latency_ms=10.0,
        transport="http",
    )
    client.call_tool = AsyncMock(return_value=fake_result)  # type: ignore[method-assign]

    result = await client.graphiti_get_entity("Alice")
    assert result == {"name": "Alice", "type": "person"}
    call_args = client.call_tool.call_args
    assert call_args[0][0] == "graphiti"
    assert call_args[0][1] == "get_entity"
    assert call_args[0][2] == {"name": "Alice"}


@pytest.mark.asyncio
async def test_kxkm_rag_search_normalizes_results_and_scope():
    settings.kxkm_rag_url = "http://localhost:3333"
    settings.mascarade_project_id = "project-alpha"
    trace_buffer = AgentTraceBuffer()
    client = McpRuntimeClient(trace_buffer=trace_buffer)

    response_body = {
        "ok": True,
        "data": {
            "results": [
                {
                    "id": "chunk-1",
                    "text": "Musique concrete\nPierre Schaeffer",
                    "score": 0.91,
                    "source_url": "http://kxkm/chunk-1",
                }
            ],
            "total": 1,
        },
    }

    mock_post = AsyncMock(return_value=_FakeResponse(response_body))
    with patch("httpx.AsyncClient") as mock_client_cls:
        ctx = AsyncMock()
        ctx.post = mock_post
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = ctx

        result = await client.kxkm_rag_search(
            "musique concrete",
            limit=5,
            project_id="project-alpha",
            run_id="run-kxkm-1",
        )

    assert result["provider"] == "kxkm"
    assert result["project_id"] == "project-alpha"
    assert result["knowledge_scope"] == "project"
    assert result["total"] == 1
    assert result["results"][0]["text"] == "Musique concrete\nPierre Schaeffer"
    assert result["results"][0]["metadata"]["project_id"] == "project-alpha"

    _, kwargs = mock_post.await_args
    assert kwargs["json"]["project_id"] == "project-alpha"
    assert kwargs["headers"]["x-mascarade-project-id"] == "project-alpha"
    assert kwargs["headers"]["x-mascarade-federation-scope"] == "project-alpha"

    events = trace_buffer.run_events("run-kxkm-1")
    assert [event.event_type for event in events][-2:] == [
        "mcp_call_started",
        "mcp_call_completed",
    ]
    assert events[-1].mcp_server == "kxkm"
    assert events[-1].mcp_tool == "kxkm_rag_search"
    assert events[-1].mcp_transport == "http-rest"


@pytest.mark.asyncio
async def test_knowledge_base_search_dispatches_to_kxkm():
    settings.knowledge_base_provider = "kxkm"
    client = McpRuntimeClient()
    client.kxkm_rag_search = AsyncMock(return_value={"provider": "kxkm", "results": []})  # type: ignore[method-assign]

    result = await client.knowledge_base_search(
        "hello",
        limit=3,
        project_id="project-beta",
        federation_scope=["project-beta"],
    )

    assert result["provider"] == "kxkm"
    client.kxkm_rag_search.assert_awaited_once_with(
        "hello",
        limit=3,
        project_id="project-beta",
        federation_scope=["project-beta"],
        knowledge_scope="project",
        run_id=None,
        mode="internal",
        step=0,
        agent_name=None,
    )
