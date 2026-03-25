"""Tests for mascarade.mcp.kicad_seeed — Seeed Studio KiCad MCP server integration."""

from __future__ import annotations

from unittest.mock import patch

from mascarade.mcp.kicad_seeed import (
    LEGACY_OVERLAP_TOOLS,
    SEEED_TOOL_CATEGORIES,
    SEEED_TOOLS,
    SeeedKicadServer,
    get_server,
    get_server_config,
    get_tools_by_category,
    is_available,
    resolve_tool,
)

# ---------------------------------------------------------------------------
# SEEED_TOOLS catalogue
# ---------------------------------------------------------------------------


class TestToolCatalogue:
    def test_tool_count(self):
        assert len(SEEED_TOOLS) == 37

    def test_expected_categories(self):
        expected = {
            "schematic_analysis",
            "hierarchical_analysis",
            "pcb_analysis",
            "netlist_analysis",
            "validation",
            "pin_analysis",
            "device_tree",
            "editing",
            "pcb_layout",
            "project_management",
        }
        assert set(SEEED_TOOL_CATEGORIES.keys()) == expected

    def test_tools_flat_list_matches_categories(self):
        from_cats = [t for tools in SEEED_TOOL_CATEGORIES.values() for t in tools]
        assert from_cats == SEEED_TOOLS

    def test_no_duplicate_tools(self):
        assert len(SEEED_TOOLS) == len(set(SEEED_TOOLS))

    def test_validation_category_has_drc_erc(self):
        validation = SEEED_TOOL_CATEGORIES["validation"]
        assert "run_drc" in validation
        assert "run_erc" in validation

    def test_editing_category(self):
        editing = SEEED_TOOL_CATEGORIES["editing"]
        assert "add_component_from_library" in editing
        assert "add_wire" in editing


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    def test_available_when_uvx_exists(self):
        with (
            patch("mascarade.mcp.kicad_seeed._is_enabled", return_value=True),
            patch("shutil.which", return_value="/usr/bin/uvx"),
        ):
            assert is_available() is True

    def test_not_available_without_uvx(self):
        with (
            patch("mascarade.mcp.kicad_seeed._is_enabled", return_value=True),
            patch("shutil.which", return_value=None),
        ):
            assert is_available() is False

    def test_not_available_when_disabled(self):
        with patch("mascarade.mcp.kicad_seeed._is_enabled", return_value=False):
            assert is_available() is False

    def test_disabled_via_env(self):
        with patch.dict("os.environ", {"KICAD_MCP_SEEED_ENABLED": "false"}):
            # Re-import would be needed for full coverage, but _is_enabled reads env directly
            from mascarade.mcp.kicad_seeed import _is_enabled
            assert _is_enabled() is False


# ---------------------------------------------------------------------------
# get_server_config
# ---------------------------------------------------------------------------


class TestGetServerConfig:
    def test_returns_dict(self):
        config = get_server_config()
        assert isinstance(config, dict)
        assert "key" in config
        assert "command" in config
        assert "transport" in config

    def test_key_is_seeed_kicad_v2(self):
        config = get_server_config()
        assert config["key"] == "seeed-kicad-v2"

    def test_transport_is_stdio(self):
        config = get_server_config()
        assert config["transport"] == "stdio"

    def test_project_path_injected(self):
        config = get_server_config(project_path="/home/user/mypcb")
        assert config["env"]["KICAD_PROJECT_PATH"] == "/home/user/mypcb"

    def test_no_project_path_empty_env(self):
        config = get_server_config()
        assert config["env"] == {}

    def test_timeout_present(self):
        config = get_server_config()
        assert config["timeout_s"] == 60.0


# ---------------------------------------------------------------------------
# resolve_tool
# ---------------------------------------------------------------------------


class TestResolveTool:
    def test_canonical_name_returns_itself(self):
        assert resolve_tool("run_drc") == "run_drc"

    def test_legacy_name_maps(self):
        assert resolve_tool("check_drc") == "run_drc"
        assert resolve_tool("analyze_schematic") == "list_schematic_components"

    def test_unknown_returns_none(self):
        assert resolve_tool("nonexistent_tool_xyz") is None

    def test_all_legacy_tools_resolve(self):
        for legacy, expected in LEGACY_OVERLAP_TOOLS.items():
            assert resolve_tool(legacy) == expected


# ---------------------------------------------------------------------------
# get_tools_by_category
# ---------------------------------------------------------------------------


class TestGetToolsByCategory:
    def test_known_category(self):
        tools = get_tools_by_category("validation")
        assert "run_drc" in tools
        assert len(tools) == 6

    def test_unknown_category(self):
        assert get_tools_by_category("nonexistent") == []


# ---------------------------------------------------------------------------
# SeeedKicadServer dataclass
# ---------------------------------------------------------------------------


class TestSeeedKicadServer:
    def test_default_values(self):
        srv = SeeedKicadServer()
        assert srv.key == "seeed-kicad-v2"
        assert srv.transport == "stdio"
        assert len(srv.tools) == 37

    def test_get_server_singleton_reset(self):
        """get_server() returns a SeeedKicadServer instance."""
        import mascarade.mcp.kicad_seeed as mod
        old = mod._server
        mod._server = None
        try:
            srv = get_server()
            assert isinstance(srv, SeeedKicadServer)
        finally:
            mod._server = old

    def test_custom_command_via_env(self):
        with patch.dict("os.environ", {"KICAD_MCP_SEEED_COMMAND": "python3 -m kicad_mcp_server"}):
            from mascarade.mcp.kicad_seeed import _resolve_command
            cmd = _resolve_command()
            assert cmd == ("python3", "-m", "kicad_mcp_server")
