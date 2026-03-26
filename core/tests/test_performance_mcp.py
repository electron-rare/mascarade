"""Tests for mascarade.mcp.performance and mascarade.routers.performance."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.mcp.performance import (
    PerformanceMcpManager,
    PerformanceStatus,
    TransportAction,
)

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class TestTransportAction:
    def test_values(self):
        assert TransportAction.PLAY == "play"
        assert TransportAction.STOP == "stop"
        assert TransportAction.PAUSE == "pause"
        assert TransportAction.RECORD == "record"
        assert TransportAction.REWIND == "rewind"

    def test_from_string(self):
        assert TransportAction("play") is TransportAction.PLAY


class TestPerformanceStatus:
    def test_defaults(self):
        s = PerformanceStatus()
        assert s.daw_connected is False
        assert s.daw_transport == "stopped"
        assert s.daw_bpm is None
        assert s.dmx_connected is False
        assert s.dmx_blackout is False
        assert s.obs_connected is False
        assert s.obs_streaming is False

    def test_custom_values(self):
        s = PerformanceStatus(
            daw_connected=True,
            daw_transport="playing",
            daw_bpm=120.0,
            dmx_connected=True,
            dmx_active_scene="warm",
            obs_connected=True,
            obs_streaming=True,
        )
        assert s.daw_bpm == 120.0
        assert s.dmx_active_scene == "warm"
        assert s.obs_streaming is True


# ---------------------------------------------------------------------------
# PerformanceMcpManager
# ---------------------------------------------------------------------------


class TestPerformanceMcpManager:
    @pytest.fixture()
    def mock_mcp(self):
        mcp = MagicMock()
        mcp._servers = {}
        mcp.call_tool = AsyncMock()
        return mcp

    @pytest.fixture()
    def manager(self, mock_mcp):
        return PerformanceMcpManager(mock_mcp)

    def test_register_disabled(self, manager):
        with patch.dict("os.environ", {"PERFORMANCE_MCP_ENABLED": ""}):
            registered = manager.register()
            assert registered == []
            assert manager.available_servers == []

    def test_register_enabled_with_daw(self, manager):
        env = {
            "PERFORMANCE_MCP_ENABLED": "true",
            "REAPER_MCP_COMMAND": "node reaper-server.js",
        }
        with patch.dict("os.environ", env, clear=True):
            registered = manager.register()
            assert "performance-daw" in registered
            assert manager.is_available("performance-daw")
            assert not manager.is_available("performance-dmx")

    def test_register_all_servers(self, manager):
        env = {
            "PERFORMANCE_MCP_ENABLED": "true",
            "REAPER_MCP_COMMAND": "node reaper.js",
            "LACYLIGHTS_MCP_COMMAND": "node lacy.js",
            "OBS_MCP_COMMAND": "node obs.js",
        }
        with patch.dict("os.environ", env, clear=True):
            registered = manager.register()
            assert len(registered) == 3
            assert manager.is_available("performance-daw")
            assert manager.is_available("performance-dmx")
            assert manager.is_available("performance-obs")

    def test_register_enabled_no_commands(self, manager):
        env = {"PERFORMANCE_MCP_ENABLED": "true"}
        with patch.dict("os.environ", env, clear=True):
            registered = manager.register()
            assert registered == []

    @pytest.mark.asyncio
    async def test_daw_transport_not_available(self, manager):
        from mascarade.mcp.errors import McpServerUnavailable

        with pytest.raises(McpServerUnavailable):
            await manager.daw_transport(TransportAction.PLAY)

    @pytest.mark.asyncio
    async def test_daw_transport_play(self, manager, mock_mcp):
        # Register DAW
        env = {
            "PERFORMANCE_MCP_ENABLED": "true",
            "REAPER_MCP_COMMAND": "node reaper.js",
        }
        with patch.dict("os.environ", env, clear=True):
            manager.register()

        mock_result = MagicMock()
        mock_result.structured_content = {"state": "playing"}
        mock_result.is_error = False
        mock_mcp.call_tool.return_value = mock_result

        await manager.daw_transport(TransportAction.PLAY, bpm=120.0)
        mock_mcp.call_tool.assert_called_once_with(
            "performance-daw",
            "transport_control",
            {"action": "play", "bpm": 120.0},
        )

    @pytest.mark.asyncio
    async def test_daw_get_status_not_available(self, manager):
        status = await manager.daw_get_status()
        assert status == {"connected": False}

    @pytest.mark.asyncio
    async def test_daw_get_status_success(self, manager, mock_mcp):
        env = {
            "PERFORMANCE_MCP_ENABLED": "true",
            "REAPER_MCP_COMMAND": "node reaper.js",
        }
        with patch.dict("os.environ", env, clear=True):
            manager.register()

        mock_result = MagicMock()
        mock_result.structured_content = {"state": "playing", "bpm": 120.0}
        mock_mcp.call_tool.return_value = mock_result

        status = await manager.daw_get_status()
        assert status["connected"] is True
        assert status["state"] == "playing"

    @pytest.mark.asyncio
    async def test_daw_get_status_error(self, manager, mock_mcp):
        env = {
            "PERFORMANCE_MCP_ENABLED": "true",
            "REAPER_MCP_COMMAND": "node reaper.js",
        }
        with patch.dict("os.environ", env, clear=True):
            manager.register()

        mock_mcp.call_tool.side_effect = RuntimeError("connection failed")
        status = await manager.daw_get_status()
        assert status["connected"] is False
        assert "error" in status

    @pytest.mark.asyncio
    async def test_dmx_trigger_scene(self, manager, mock_mcp):
        env = {
            "PERFORMANCE_MCP_ENABLED": "true",
            "LACYLIGHTS_MCP_COMMAND": "node lacy.js",
        }
        with patch.dict("os.environ", env, clear=True):
            manager.register()

        mock_result = MagicMock()
        mock_mcp.call_tool.return_value = mock_result

        await manager.dmx_trigger_scene("warm", fade_ms=500, universe=1)
        mock_mcp.call_tool.assert_called_once_with(
            "performance-dmx",
            "trigger_scene",
            {"scene_name": "warm", "fade_ms": 500, "universe": 1},
        )

    @pytest.mark.asyncio
    async def test_dmx_blackout(self, manager, mock_mcp):
        env = {
            "PERFORMANCE_MCP_ENABLED": "true",
            "LACYLIGHTS_MCP_COMMAND": "node lacy.js",
        }
        with patch.dict("os.environ", env, clear=True):
            manager.register()

        mock_result = MagicMock()
        mock_mcp.call_tool.return_value = mock_result

        await manager.dmx_blackout(fade_ms=100)
        mock_mcp.call_tool.assert_called_once_with(
            "performance-dmx",
            "blackout",
            {"fade_ms": 100},
        )

    @pytest.mark.asyncio
    async def test_obs_switch_scene(self, manager, mock_mcp):
        env = {
            "PERFORMANCE_MCP_ENABLED": "true",
            "OBS_MCP_COMMAND": "node obs.js",
        }
        with patch.dict("os.environ", env, clear=True):
            manager.register()

        mock_result = MagicMock()
        mock_mcp.call_tool.return_value = mock_result

        await manager.obs_switch_scene("main_camera")
        mock_mcp.call_tool.assert_called_once_with(
            "performance-obs",
            "switch_scene",
            {"scene_name": "main_camera"},
        )

    @pytest.mark.asyncio
    async def test_get_full_status_all_disconnected(self, manager):
        status = await manager.get_full_status()
        assert isinstance(status, PerformanceStatus)
        assert status.daw_connected is False
        assert status.dmx_connected is False
        assert status.obs_connected is False

    @pytest.mark.asyncio
    async def test_get_full_status_all_connected(self, manager, mock_mcp):
        env = {
            "PERFORMANCE_MCP_ENABLED": "true",
            "REAPER_MCP_COMMAND": "node reaper.js",
            "LACYLIGHTS_MCP_COMMAND": "node lacy.js",
            "OBS_MCP_COMMAND": "node obs.js",
        }
        with patch.dict("os.environ", env, clear=True):
            manager.register()

        def make_result(content):
            r = MagicMock()
            r.structured_content = content
            return r

        mock_mcp.call_tool.side_effect = [
            make_result({"state": "playing", "bpm": 120.0, "position": 30.0}),
            make_result({"active_scene": "warm", "universes": [1, 2], "blackout": False}),
            make_result({"streaming": True, "recording": False, "active_scene": "main"}),
        ]

        status = await manager.get_full_status()
        assert status.daw_connected is True
        assert status.daw_bpm == 120.0
        assert status.dmx_connected is True
        assert status.dmx_active_scene == "warm"
        assert status.obs_connected is True
        assert status.obs_streaming is True


# ---------------------------------------------------------------------------
# Performance router endpoints
# ---------------------------------------------------------------------------


class TestPerformanceRouter:
    @pytest.fixture()
    def mock_app(self):

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from mascarade.routers.performance import router as perf_router

        app = FastAPI()
        app.include_router(perf_router)

        mock_manager = MagicMock(spec=PerformanceMcpManager)
        mock_manager.SERVER_KEY_DAW = PerformanceMcpManager.SERVER_KEY_DAW
        mock_manager.SERVER_KEY_DMX = PerformanceMcpManager.SERVER_KEY_DMX
        mock_manager.SERVER_KEY_OBS = PerformanceMcpManager.SERVER_KEY_OBS
        mock_manager.is_available.return_value = True
        mock_manager.available_servers = ["performance-daw", "performance-dmx"]

        app.state.performance_mcp = mock_manager

        return TestClient(app), mock_manager

    def test_daw_transport_play(self, mock_app):
        client, mock_manager = mock_app
        mock_result = MagicMock()
        mock_result.is_error = False
        mock_result.server_key = "performance-daw"
        mock_result.tool_name = "transport_control"
        mock_result.message = "ok"
        mock_result.structured_content = {"state": "playing"}
        mock_result.latency_ms = 15.0
        mock_manager.daw_transport = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/v1/performance/daw/transport",
            json={"action": "play"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_daw_transport_invalid_action(self, mock_app):
        client, _ = mock_app
        resp = client.post(
            "/v1/performance/daw/transport",
            json={"action": "dance"},
        )
        assert resp.status_code == 422  # validation error

    def test_dmx_scene(self, mock_app):
        client, mock_manager = mock_app
        mock_result = MagicMock()
        mock_result.is_error = False
        mock_result.server_key = "performance-dmx"
        mock_result.tool_name = "trigger_scene"
        mock_result.message = "ok"
        mock_result.structured_content = {}
        mock_result.latency_ms = 10.0
        mock_manager.dmx_trigger_scene = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/v1/performance/dmx/scene",
            json={"scene_name": "warm", "fade_ms": 500},
        )
        assert resp.status_code == 200

    def test_obs_scene(self, mock_app):
        client, mock_manager = mock_app
        mock_result = MagicMock()
        mock_result.is_error = False
        mock_result.server_key = "performance-obs"
        mock_result.tool_name = "switch_scene"
        mock_result.message = "ok"
        mock_result.structured_content = {}
        mock_result.latency_ms = 5.0
        mock_manager.obs_switch_scene = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/v1/performance/obs/scene",
            json={"scene_name": "main_camera"},
        )
        assert resp.status_code == 200

    def test_performance_status(self, mock_app):
        client, mock_manager = mock_app
        mock_manager.get_full_status = AsyncMock(return_value=PerformanceStatus())

        resp = client.get("/v1/performance/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "performance" in data
        assert "servers" in data

    def test_not_configured(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from mascarade.routers.performance import router as perf_router

        app = FastAPI()
        app.include_router(perf_router)
        # No performance_mcp in app state
        client = TestClient(app)

        resp = client.post(
            "/v1/performance/daw/transport",
            json={"action": "play"},
        )
        assert resp.status_code == 503
