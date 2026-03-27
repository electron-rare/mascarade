"""Tests for KiCad MCP server registry and router endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.mcp.kicad_servers import (
    KICAD_MCP_SERVERS,
    KiCadMcpServer,
    discover_installed,
    get_server_config,
    log_available,
)

# ---------------------------------------------------------------------------
# Unit tests for kicad_servers module
# ---------------------------------------------------------------------------


class TestKicadServerRegistry:
    def test_all_servers_defined(self):
        expected_keys = {
            "seeed-kicad",
            "seeed-kicad-v2",
            "circuit-synth",
            "kicad-happy",
            "mixelpixx-kicad",
            "spicebridge",
        }
        assert set(KICAD_MCP_SERVERS.keys()) == expected_keys

    def test_server_dataclass_fields(self):
        for key, srv in KICAD_MCP_SERVERS.items():
            assert isinstance(srv, KiCadMcpServer)
            assert srv.key == key
            assert srv.description
            assert srv.repo.startswith("https://")
            assert len(srv.command) >= 2
            assert srv.tools  # every server exposes at least one tool

    def test_spicebridge_has_many_tools(self):
        sb = KICAD_MCP_SERVERS["spicebridge"]
        assert len(sb.tools) >= 10

    @patch("mascarade.mcp.kicad_servers.shutil.which")
    def test_discover_installed_npx_available(self, mock_which):
        mock_which.side_effect = lambda cmd: "/usr/bin/npx" if cmd == "npx" else None
        installed = discover_installed()
        # seeed-kicad and circuit-synth use npx
        assert "seeed-kicad" in installed
        assert "circuit-synth" in installed
        # python3-based servers should not be found
        assert "kicad-happy" not in installed

    @patch("mascarade.mcp.kicad_servers.shutil.which")
    def test_discover_installed_python3_available(self, mock_which):
        mock_which.side_effect = lambda cmd: "/usr/bin/python3" if cmd == "python3" else None
        installed = discover_installed()
        assert "kicad-happy" in installed
        assert "mixelpixx-kicad" in installed
        assert "spicebridge" in installed
        assert "seeed-kicad" not in installed

    @patch("mascarade.mcp.kicad_servers.shutil.which", return_value=None)
    def test_discover_installed_nothing(self, mock_which):
        installed = discover_installed()
        assert installed == []

    def test_get_server_config_basic(self):
        cfg = get_server_config("spicebridge")
        assert cfg["key"] == "spicebridge"
        assert cfg["transport"] == "stdio"
        assert cfg["timeout_s"] == 45.0
        assert cfg["env"] == {}

    def test_get_server_config_with_project_path(self):
        cfg = get_server_config("seeed-kicad", project_path="/tmp/my_board")
        assert cfg["env"]["KICAD_PROJECT_PATH"] == "/tmp/my_board"

    def test_get_server_config_unknown_raises(self):
        with pytest.raises(KeyError):
            get_server_config("nonexistent-server")

    @patch("mascarade.mcp.kicad_servers.shutil.which", return_value="/usr/bin/npx")
    def test_log_available_some(self, mock_which, caplog):
        import logging

        with caplog.at_level(logging.INFO, logger="mascarade.mcp.kicad_servers"):
            log_available()
        assert "KiCad MCP servers" in caplog.text

    @patch("mascarade.mcp.kicad_servers.shutil.which", return_value=None)
    def test_log_available_none(self, mock_which, caplog):
        import logging

        with caplog.at_level(logging.INFO, logger="mascarade.mcp.kicad_servers"):
            log_available()
        assert "No KiCad MCP servers installed" in caplog.text


# ---------------------------------------------------------------------------
# Router endpoint tests (FastAPI TestClient)
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """Create a FastAPI TestClient with mocked auth and MCP."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from mascarade.auth import require_auth
    from mascarade.routers.kicad_mcp import router

    test_app = FastAPI()
    test_app.include_router(router)

    # Override the auth dependency to be a no-op
    test_app.dependency_overrides[require_auth] = lambda: None

    mock_mcp = AsyncMock()
    test_app.state.mcp = mock_mcp

    yield TestClient(test_app), mock_mcp

    test_app.dependency_overrides.clear()


class TestKicadRouter:
    @patch(
        "mascarade.routers.kicad_mcp.discover_installed",
        return_value=["seeed-kicad", "spicebridge"],
    )
    def test_list_servers(self, mock_discover, client):
        test_client, _ = client
        resp = test_client.get("/v1/api/kicad/servers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == len(KICAD_MCP_SERVERS)
        assert data["installed_count"] == 2
        # Check that server entries have the right keys
        srv = data["servers"][0]
        assert "key" in srv
        assert "installed" in srv
        assert "tools" in srv

    @patch(
        "mascarade.routers.kicad_mcp.discover_installed",
        return_value=["seeed-kicad", "spicebridge"],
    )
    def test_list_tools(self, mock_discover, client):
        test_client, _ = client
        resp = test_client.get("/v1/api/kicad/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] > 0
        # All returned tools should be from installed servers
        for t in data["tools"]:
            assert t["server"] in ("seeed-kicad", "spicebridge")

    @patch("mascarade.routers.kicad_mcp.discover_installed", return_value=["seeed-kicad"])
    def test_analyze_project(self, mock_discover, client):
        test_client, mock_mcp = client
        mock_result = MagicMock()
        mock_result.content = {"components": 42, "nets": 10}
        mock_mcp.call_tool.return_value = mock_result

        resp = test_client.post(
            "/v1/api/kicad/analyze",
            json={"project_path": "/tmp/test.kicad_pro"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["server"] == "seeed-kicad"
        assert data["tool"] == "analyze_schematic"
        mock_mcp.call_tool.assert_called_once()

    @patch("mascarade.routers.kicad_mcp.discover_installed", return_value=[])
    def test_analyze_no_server(self, mock_discover, client):
        test_client, _ = client
        resp = test_client.post(
            "/v1/api/kicad/analyze",
            json={"project_path": "/tmp/test.kicad_pro"},
        )
        assert resp.status_code == 503

    @patch("mascarade.routers.kicad_mcp.discover_installed", return_value=["seeed-kicad"])
    def test_drc(self, mock_discover, client):
        test_client, mock_mcp = client
        mock_result = MagicMock()
        mock_result.content = {"errors": 0, "warnings": 2}
        mock_mcp.call_tool.return_value = mock_result

        resp = test_client.post(
            "/v1/api/kicad/drc",
            json={"project_path": "/tmp/test.kicad_pro"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["server"] == "seeed-kicad"
        assert data["tool"] == "check_drc"

    @patch("mascarade.routers.kicad_mcp.discover_installed", return_value=["spicebridge"])
    def test_spice_simulation(self, mock_discover, client):
        test_client, mock_mcp = client
        mock_result = MagicMock()
        mock_result.content = {"waveform": [0.0, 1.1, 2.2]}
        mock_mcp.call_tool.return_value = mock_result

        resp = test_client.post(
            "/v1/api/kicad/spice",
            json={"netlist": "* test circuit\nV1 1 0 5", "analysis": "ac"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["server"] == "spicebridge"
        assert data["tool"] == "run_ac_analysis"
        assert data["analysis"] == "ac"

    @patch("mascarade.routers.kicad_mcp.discover_installed", return_value=["spicebridge"])
    def test_spice_invalid_analysis(self, mock_discover, client):
        test_client, _ = client
        resp = test_client.post(
            "/v1/api/kicad/spice",
            json={"analysis": "invalid_type"},
        )
        assert resp.status_code == 400

    @patch("mascarade.routers.kicad_mcp.discover_installed", return_value=[])
    def test_spice_no_server(self, mock_discover, client):
        test_client, _ = client
        resp = test_client.post(
            "/v1/api/kicad/spice",
            json={"analysis": "transient"},
        )
        assert resp.status_code == 503
