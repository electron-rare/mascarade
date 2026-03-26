"""Performance MCP clients — Reaper DAW, LacyLights DMX, OBS streaming.

Connects to external MCP servers for live performance control in the
kxkm_clown multimodal system.  Each server is opt-in and registered only
when the corresponding env var is set.

MCP server references:
  - Reaper:     https://github.com/dschuler36/reaper-mcp-server
  - LacyLights: https://github.com/bbernstein/lacylights-mcp
  - OBS:        https://github.com/royshil/obs-mcp
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mascarade.mcp.client import McpRuntimeClient
from mascarade.mcp.server_registry import McpServerDefinition, McpToolResult

logger = logging.getLogger("mascarade.mcp.performance")


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class TransportAction(str, Enum):
    PLAY = "play"
    STOP = "stop"
    PAUSE = "pause"
    RECORD = "record"
    REWIND = "rewind"


@dataclass(slots=True)
class PerformanceStatus:
    """Aggregate status of all performance subsystems."""

    daw_connected: bool = False
    daw_transport: str = "stopped"
    daw_bpm: float | None = None
    daw_position: float | None = None

    dmx_connected: bool = False
    dmx_active_scene: str | None = None
    dmx_universes: list[int] = field(default_factory=list)
    dmx_blackout: bool = False

    obs_connected: bool = False
    obs_streaming: bool = False
    obs_recording: bool = False
    obs_active_scene: str | None = None


# ---------------------------------------------------------------------------
# Performance MCP Manager
# ---------------------------------------------------------------------------


class PerformanceMcpManager:
    """Unified interface to performance MCP servers.

    Lazily registers Reaper / LacyLights / OBS MCP servers on the shared
    McpRuntimeClient when ``register()`` is called (typically at app startup).
    All public methods are async and safe to call even when a server is
    unavailable — they return sensible defaults or raise informative errors.
    """

    SERVER_KEY_DAW = "performance-daw"
    SERVER_KEY_DMX = "performance-dmx"
    SERVER_KEY_OBS = "performance-obs"

    def __init__(self, mcp_client: McpRuntimeClient) -> None:
        self._mcp = mcp_client
        self._registered_keys: set[str] = set()

    # -- Registration -------------------------------------------------------

    def register(self) -> list[str]:
        """Register performance MCP servers based on env vars.

        Returns:
            List of server keys that were successfully registered.
        """
        enabled = os.getenv("PERFORMANCE_MCP_ENABLED", "").lower()
        if enabled not in ("1", "true", "yes"):
            logger.info("Performance MCP disabled (PERFORMANCE_MCP_ENABLED != true)")
            return []

        registered: list[str] = []

        reaper_cmd = os.getenv("REAPER_MCP_COMMAND", "").strip()
        if reaper_cmd:
            self._register_server(
                key=self.SERVER_KEY_DAW,
                command=tuple(reaper_cmd.split()),
                label="Reaper DAW",
                description=(
                    "REAPER DAW control via MCP — transport, tracks, effects, markers. "
                    "https://github.com/dschuler36/reaper-mcp-server"
                ),
                timeout_s=30.0,
            )
            registered.append(self.SERVER_KEY_DAW)

        lacylights_cmd = os.getenv("LACYLIGHTS_MCP_COMMAND", "").strip()
        if lacylights_cmd:
            self._register_server(
                key=self.SERVER_KEY_DMX,
                command=tuple(lacylights_cmd.split()),
                label="LacyLights DMX",
                description=(
                    "DMX lighting control via MCP — universes, fixtures, scenes, cues. "
                    "https://github.com/bbernstein/lacylights-mcp"
                ),
                timeout_s=20.0,
            )
            registered.append(self.SERVER_KEY_DMX)

        obs_cmd = os.getenv("OBS_MCP_COMMAND", "").strip()
        if obs_cmd:
            self._register_server(
                key=self.SERVER_KEY_OBS,
                command=tuple(obs_cmd.split()),
                label="OBS Studio",
                description=(
                    "OBS Studio streaming/recording control via MCP — scenes, sources, recording. "
                    "https://github.com/royshil/obs-mcp"
                ),
                timeout_s=20.0,
            )
            registered.append(self.SERVER_KEY_OBS)

        if registered:
            logger.info("Performance MCP servers registered: %s", registered)
        else:
            logger.warning("PERFORMANCE_MCP_ENABLED=true but no server commands configured")

        return registered

    def _register_server(
        self,
        *,
        key: str,
        command: tuple[str, ...],
        label: str,
        description: str,
        timeout_s: float,
    ) -> None:
        self._mcp._servers[key] = McpServerDefinition(
            key=key,
            command=command,
            timeout_s=timeout_s,
            label=label,
            description=description,
        )
        self._registered_keys.add(key)

    @property
    def available_servers(self) -> list[str]:
        return sorted(self._registered_keys)

    def is_available(self, key: str) -> bool:
        return key in self._registered_keys

    # -- DAW (Reaper) -------------------------------------------------------

    async def daw_transport(
        self, action: TransportAction, *, bpm: float | None = None
    ) -> McpToolResult:
        """Control DAW transport (play/stop/pause/record/rewind)."""
        args: dict[str, Any] = {"action": action.value}
        if bpm is not None:
            args["bpm"] = bpm
        return await self._call(self.SERVER_KEY_DAW, "transport_control", args)

    async def daw_get_tracks(self) -> McpToolResult:
        """List all tracks in the current Reaper project."""
        return await self._call(self.SERVER_KEY_DAW, "get_tracks", {})

    async def daw_set_track_volume(self, track_index: int, volume_db: float) -> McpToolResult:
        """Set volume for a specific track."""
        return await self._call(
            self.SERVER_KEY_DAW,
            "set_track_volume",
            {"track_index": track_index, "volume_db": volume_db},
        )

    async def daw_add_marker(
        self, position: float, name: str, color: str | None = None
    ) -> McpToolResult:
        """Add a marker at a position (seconds) in the timeline."""
        args: dict[str, Any] = {"position": position, "name": name}
        if color:
            args["color"] = color
        return await self._call(self.SERVER_KEY_DAW, "add_marker", args)

    async def daw_get_status(self) -> dict[str, Any]:
        """Get current DAW status (transport state, position, BPM)."""
        if not self.is_available(self.SERVER_KEY_DAW):
            return {"connected": False}
        try:
            result = await self._call(self.SERVER_KEY_DAW, "get_transport_state", {})
            return {"connected": True, **result.structured_content}
        except Exception as exc:
            logger.warning("DAW status check failed: %s", exc)
            return {"connected": False, "error": str(exc)}

    # -- DMX (LacyLights) ---------------------------------------------------

    async def dmx_trigger_scene(
        self,
        scene_name: str,
        *,
        fade_ms: int = 0,
        universe: int | None = None,
    ) -> McpToolResult:
        """Trigger a named lighting scene."""
        args: dict[str, Any] = {"scene_name": scene_name, "fade_ms": fade_ms}
        if universe is not None:
            args["universe"] = universe
        return await self._call(self.SERVER_KEY_DMX, "trigger_scene", args)

    async def dmx_blackout(self, *, fade_ms: int = 0) -> McpToolResult:
        """Emergency blackout — all channels to zero."""
        return await self._call(self.SERVER_KEY_DMX, "blackout", {"fade_ms": fade_ms})

    async def dmx_set_fixture(
        self,
        fixture_id: str,
        *,
        intensity: float | None = None,
        color: str | None = None,
        position: dict[str, float] | None = None,
    ) -> McpToolResult:
        """Set a single fixture's properties."""
        args: dict[str, Any] = {"fixture_id": fixture_id}
        if intensity is not None:
            args["intensity"] = intensity
        if color is not None:
            args["color"] = color
        if position is not None:
            args["position"] = position
        return await self._call(self.SERVER_KEY_DMX, "set_fixture", args)

    async def dmx_list_scenes(self) -> McpToolResult:
        """List all available lighting scenes."""
        return await self._call(self.SERVER_KEY_DMX, "list_scenes", {})

    async def dmx_get_status(self) -> dict[str, Any]:
        """Get current DMX status."""
        if not self.is_available(self.SERVER_KEY_DMX):
            return {"connected": False}
        try:
            result = await self._call(self.SERVER_KEY_DMX, "get_status", {})
            return {"connected": True, **result.structured_content}
        except Exception as exc:
            logger.warning("DMX status check failed: %s", exc)
            return {"connected": False, "error": str(exc)}

    # -- OBS (optional) -----------------------------------------------------

    async def obs_switch_scene(self, scene_name: str) -> McpToolResult:
        """Switch OBS to a named scene."""
        return await self._call(self.SERVER_KEY_OBS, "switch_scene", {"scene_name": scene_name})

    async def obs_start_recording(self) -> McpToolResult:
        return await self._call(self.SERVER_KEY_OBS, "start_recording", {})

    async def obs_stop_recording(self) -> McpToolResult:
        return await self._call(self.SERVER_KEY_OBS, "stop_recording", {})

    async def obs_start_streaming(self) -> McpToolResult:
        return await self._call(self.SERVER_KEY_OBS, "start_streaming", {})

    async def obs_stop_streaming(self) -> McpToolResult:
        return await self._call(self.SERVER_KEY_OBS, "stop_streaming", {})

    async def obs_get_status(self) -> dict[str, Any]:
        """Get current OBS status."""
        if not self.is_available(self.SERVER_KEY_OBS):
            return {"connected": False}
        try:
            result = await self._call(self.SERVER_KEY_OBS, "get_status", {})
            return {"connected": True, **result.structured_content}
        except Exception as exc:
            logger.warning("OBS status check failed: %s", exc)
            return {"connected": False, "error": str(exc)}

    # -- Aggregate ----------------------------------------------------------

    async def get_full_status(self) -> PerformanceStatus:
        """Aggregate status from all connected performance systems."""
        status = PerformanceStatus()

        daw = await self.daw_get_status()
        status.daw_connected = daw.get("connected", False)
        status.daw_transport = daw.get("state", "stopped")
        status.daw_bpm = daw.get("bpm")
        status.daw_position = daw.get("position")

        dmx = await self.dmx_get_status()
        status.dmx_connected = dmx.get("connected", False)
        status.dmx_active_scene = dmx.get("active_scene")
        status.dmx_universes = dmx.get("universes", [])
        status.dmx_blackout = dmx.get("blackout", False)

        obs = await self.obs_get_status()
        status.obs_connected = obs.get("connected", False)
        status.obs_streaming = obs.get("streaming", False)
        status.obs_recording = obs.get("recording", False)
        status.obs_active_scene = obs.get("active_scene")

        return status

    # -- Internal -----------------------------------------------------------

    async def _call(
        self, server_key: str, tool_name: str, arguments: dict[str, Any]
    ) -> McpToolResult:
        if not self.is_available(server_key):
            from mascarade.mcp.errors import McpServerUnavailable

            raise McpServerUnavailable(
                f"Performance MCP server '{server_key}' is not configured",
                server_key=server_key,
                tool_name=tool_name,
            )
        return await self._mcp.call_tool(server_key, tool_name, arguments)
