"""Tests for mascarade.mcp.narrative and mascarade.routers.narrative."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.mcp.narrative import (
    NarrativeMcpClient,
    _is_enabled,
    _parse_command,
    _StdioSession,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_is_enabled_true(self):
        with patch.dict("os.environ", {"NARRATIVE_MCP_ENABLED": "true"}):
            assert _is_enabled() is True

    def test_is_enabled_false(self):
        with patch.dict("os.environ", {"NARRATIVE_MCP_ENABLED": ""}):
            assert _is_enabled() is False

    def test_is_enabled_yes(self):
        with patch.dict("os.environ", {"NARRATIVE_MCP_ENABLED": "YES"}):
            assert _is_enabled() is True

    def test_parse_command_empty(self):
        with patch.dict("os.environ", {"MY_CMD": ""}):
            assert _parse_command("MY_CMD") is None

    def test_parse_command_simple(self):
        with patch.dict("os.environ", {"MY_CMD": "node server.js --port 3000"}):
            result = _parse_command("MY_CMD")
            assert result == ("node", "server.js", "--port", "3000")

    def test_parse_command_quoted(self):
        with patch.dict("os.environ", {"MY_CMD": 'python "my script.py"'}):
            result = _parse_command("MY_CMD")
            assert result == ("python", "my script.py")


# ---------------------------------------------------------------------------
# _StdioSession
# ---------------------------------------------------------------------------


class TestStdioSession:
    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        session = _StdioSession(command=("echo",), label="test")

        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.stdin = MagicMock()
        mock_proc.stdin.write = MagicMock()
        mock_proc.stdin.drain = AsyncMock()

        response = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True, "data": "hello"}}
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline = AsyncMock(
            return_value=(json.dumps(response) + "\n").encode()
        )

        session._process = mock_proc

        result = await session.call_tool("test_tool", {"arg": "val"})
        assert result == {"ok": True, "data": "hello"}

        # Verify the request was sent correctly
        written = mock_proc.stdin.write.call_args[0][0]
        req = json.loads(written)
        assert req["method"] == "tools/call"
        assert req["params"]["name"] == "test_tool"
        assert req["params"]["arguments"] == {"arg": "val"}

    @pytest.mark.asyncio
    async def test_call_tool_error_response(self):
        session = _StdioSession(command=("echo",), label="test")

        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.stdin = MagicMock()
        mock_proc.stdin.write = MagicMock()
        mock_proc.stdin.drain = AsyncMock()

        response = {"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "not found"}}
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline = AsyncMock(
            return_value=(json.dumps(response) + "\n").encode()
        )

        session._process = mock_proc

        with pytest.raises(RuntimeError, match="MCP error"):
            await session.call_tool("missing_tool")

    @pytest.mark.asyncio
    async def test_call_tool_closed_stdout(self):
        session = _StdioSession(command=("echo",), label="test")

        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.stdin = MagicMock()
        mock_proc.stdin.write = MagicMock()
        mock_proc.stdin.drain = AsyncMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline = AsyncMock(return_value=b"")

        session._process = mock_proc

        with pytest.raises(RuntimeError, match="closed stdout"):
            await session.call_tool("test")

    @pytest.mark.asyncio
    async def test_close(self):
        session = _StdioSession(command=("echo",), label="test")
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.terminate = MagicMock()
        mock_proc.wait = AsyncMock()
        mock_proc.kill = MagicMock()
        session._process = mock_proc

        await session.close()
        mock_proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_already_exited(self):
        session = _StdioSession(command=("echo",), label="test")
        mock_proc = MagicMock()
        mock_proc.returncode = 0  # already exited
        session._process = mock_proc

        await session.close()  # should not raise


# ---------------------------------------------------------------------------
# NarrativeMcpClient
# ---------------------------------------------------------------------------


class TestNarrativeMcpClient:
    def test_disabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            client = NarrativeMcpClient()
            assert client.is_configured is False

    def test_enabled_with_commands(self):
        env = {
            "NARRATIVE_MCP_ENABLED": "true",
            "NARRATIVE_MCP_BOOK_SERIES_COMMAND": "node bs-server.js",
            "NARRATIVE_MCP_WRITER_COMMAND": "node wr-server.js",
        }
        with patch.dict("os.environ", env, clear=True):
            client = NarrativeMcpClient()
            assert client.is_configured is True
            assert client._book_series is not None
            assert client._writer is not None

    def test_enabled_partial(self):
        env = {
            "NARRATIVE_MCP_ENABLED": "true",
            "NARRATIVE_MCP_BOOK_SERIES_COMMAND": "node bs.js",
        }
        with patch.dict("os.environ", env, clear=True):
            client = NarrativeMcpClient()
            assert client.is_configured is True
            assert client._book_series is not None
            assert client._writer is None

    @pytest.mark.asyncio
    async def test_track_character_not_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            client = NarrativeMcpClient()
            with pytest.raises(RuntimeError, match="not configured"):
                await client.track_character("Alice")

    @pytest.mark.asyncio
    async def test_track_character_calls_session(self):
        env = {
            "NARRATIVE_MCP_ENABLED": "true",
            "NARRATIVE_MCP_BOOK_SERIES_COMMAND": "node bs.js",
        }
        with patch.dict("os.environ", env, clear=True):
            client = NarrativeMcpClient()
            mock_bs = MagicMock()
            mock_bs.call_tool = AsyncMock(return_value={"id": "char_1"})
            client._book_series = mock_bs

            result = await client.track_character("Alice", attributes={"hair": "blonde"})
            assert result == {"id": "char_1"}
            mock_bs.call_tool.assert_called_once_with(
                "track_character",
                {"name": "Alice", "attributes": {"hair": "blonde"}, "book_id": "default"},
            )

    @pytest.mark.asyncio
    async def test_update_plot(self):
        env = {
            "NARRATIVE_MCP_ENABLED": "true",
            "NARRATIVE_MCP_BOOK_SERIES_COMMAND": "node bs.js",
        }
        with patch.dict("os.environ", env, clear=True):
            client = NarrativeMcpClient()
            mock_bs = MagicMock()
            mock_bs.call_tool = AsyncMock(return_value={"event_id": "e1"})
            client._book_series = mock_bs

            result = await client.update_plot(
                "Alice found the key",
                chapter="ch3",
                characters_involved=["Alice"],
            )
            assert result == {"event_id": "e1"}

    @pytest.mark.asyncio
    async def test_check_consistency_both_servers(self):
        env = {
            "NARRATIVE_MCP_ENABLED": "true",
            "NARRATIVE_MCP_BOOK_SERIES_COMMAND": "node bs.js",
            "NARRATIVE_MCP_WRITER_COMMAND": "node wr.js",
        }
        with patch.dict("os.environ", env, clear=True):
            client = NarrativeMcpClient()
            mock_bs = MagicMock()
            mock_bs.call_tool = AsyncMock(
                return_value={"issues": [], "score": 1.0}
            )
            mock_wr = MagicMock()
            mock_wr.call_tool = AsyncMock(
                return_value={"issues": ["timeline mismatch"]}
            )
            client._book_series = mock_bs
            client._writer = mock_wr

            result = await client.check_consistency("Alice walked in.")
            assert result["ok"] is False
            assert len(result["issues"]) > 0

    @pytest.mark.asyncio
    async def test_check_consistency_no_servers(self):
        with patch.dict("os.environ", {}, clear=True):
            client = NarrativeMcpClient()
            with pytest.raises(RuntimeError, match="No narrative MCP servers"):
                await client.check_consistency("some text")

    @pytest.mark.asyncio
    async def test_get_world_state(self):
        env = {
            "NARRATIVE_MCP_ENABLED": "true",
            "NARRATIVE_MCP_BOOK_SERIES_COMMAND": "node bs.js",
        }
        with patch.dict("os.environ", env, clear=True):
            client = NarrativeMcpClient()
            mock_bs = MagicMock()
            mock_bs.call_tool = AsyncMock(
                return_value={"characters": [], "events": []}
            )
            client._book_series = mock_bs
            result = await client.get_world_state(book_id="book1")
            assert "characters" in result

    @pytest.mark.asyncio
    async def test_get_character_knowledge_not_configured(self):
        env = {
            "NARRATIVE_MCP_ENABLED": "true",
            "NARRATIVE_MCP_BOOK_SERIES_COMMAND": "node bs.js",
            # no writer command
        }
        with patch.dict("os.environ", env, clear=True):
            client = NarrativeMcpClient()
            with pytest.raises(RuntimeError, match="Writer MCP server not configured"):
                await client.get_character_knowledge("Alice")

    @pytest.mark.asyncio
    async def test_close(self):
        env = {
            "NARRATIVE_MCP_ENABLED": "true",
            "NARRATIVE_MCP_BOOK_SERIES_COMMAND": "node bs.js",
            "NARRATIVE_MCP_WRITER_COMMAND": "node wr.js",
        }
        with patch.dict("os.environ", env, clear=True):
            client = NarrativeMcpClient()
            mock_bs = MagicMock()
            mock_bs.close = AsyncMock()
            mock_wr = MagicMock()
            mock_wr.close = AsyncMock()
            client._book_series = mock_bs
            client._writer = mock_wr

            await client.close()
            mock_bs.close.assert_called_once()
            mock_wr.close.assert_called_once()

    def test_tool_definitions(self):
        defs = NarrativeMcpClient.tool_definitions()
        assert len(defs) == 5
        names = {d["name"] for d in defs}
        assert "narrative_track_character" in names
        assert "narrative_check_consistency" in names


# ---------------------------------------------------------------------------
# Narrative router endpoints
# ---------------------------------------------------------------------------


class TestNarrativeRouter:
    @pytest.fixture()
    def mock_app(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from mascarade.routers.narrative import router as narrative_router

        app = FastAPI()

        # Override auth dependency
        from mascarade.auth import require_auth
        app.dependency_overrides[require_auth] = lambda: None

        app.include_router(narrative_router)

        # Set up a mock narrative client in app state
        mock_client = MagicMock(spec=NarrativeMcpClient)
        mock_client.is_configured = True
        app.state.narrative_mcp = mock_client

        return TestClient(app), mock_client

    def test_track_character(self, mock_app):
        client, mock_narrative = mock_app
        mock_narrative.track_character = AsyncMock(return_value={"id": "c1"})

        resp = client.post(
            "/v1/narrative/characters",
            json={"name": "Bob", "attributes": {"age": 30}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["character"] == "Bob"

    def test_check_consistency(self, mock_app):
        client, mock_narrative = mock_app
        mock_narrative.check_consistency = AsyncMock(
            return_value={"ok": True, "issues": []}
        )

        resp = client.post(
            "/v1/narrative/consistency",
            json={"text": "Alice opened the door."},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_not_configured(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from mascarade.auth import require_auth
        from mascarade.routers.narrative import router as narrative_router

        app = FastAPI()
        app.dependency_overrides[require_auth] = lambda: None
        app.include_router(narrative_router)
        # No narrative_mcp in app state
        client = TestClient(app)

        resp = client.post(
            "/v1/narrative/characters",
            json={"name": "Bob"},
        )
        assert resp.status_code == 503
