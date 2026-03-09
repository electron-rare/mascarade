from __future__ import annotations

from pathlib import Path

import pytest

from mascarade.mcp import McpCallError, McpRuntimeClient
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
