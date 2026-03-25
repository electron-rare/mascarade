"""MCP client wrappers for narrative / ai-novel-engine servers.

Connects to two external MCP servers (opt-in, stdio transport):
  - Book Series MCP — character tracking, plot arcs, world-building
  - Writer MCP — character knowledge base, consistency checking

Requires env vars (all optional, feature is opt-in):
  NARRATIVE_MCP_ENABLED            — "true" to activate
  NARRATIVE_MCP_BOOK_SERIES_COMMAND — command to launch Book Series MCP server
  NARRATIVE_MCP_WRITER_COMMAND      — command to launch Writer MCP server
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("mascarade.mcp.narrative")


def _is_enabled() -> bool:
    return os.getenv("NARRATIVE_MCP_ENABLED", "").lower() in ("true", "1", "yes")


def _parse_command(env_var: str) -> tuple[str, ...] | None:
    raw = os.getenv(env_var, "").strip()
    if not raw:
        return None
    return tuple(shlex.split(raw))


# ---------------------------------------------------------------------------
# Lightweight subprocess-based stdio MCP caller
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class _StdioSession:
    """Manages a single stdio MCP server subprocess."""

    command: tuple[str, ...]
    label: str
    _process: asyncio.subprocess.Process | None = field(default=None, repr=False)
    _request_id: int = field(default=0, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def _ensure_process(self) -> asyncio.subprocess.Process:
        if self._process is None or self._process.returncode is not None:
            logger.info("Starting %s MCP server: %s", self.label, " ".join(self.command))
            self._process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        return self._process

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None, *, timeout: float = 30.0) -> dict[str, Any]:
        """Send a JSON-RPC tools/call request and return the result."""
        import json

        async with self._lock:
            proc = await self._ensure_process()
            assert proc.stdin is not None and proc.stdout is not None

            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments or {},
                },
            }

            payload = json.dumps(request) + "\n"
            proc.stdin.write(payload.encode())
            await proc.stdin.drain()

            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
            if not raw:
                raise RuntimeError(f"{self.label} MCP server closed stdout unexpectedly")

            response = json.loads(raw)
            if "error" in response:
                raise RuntimeError(f"{self.label} MCP error: {response['error']}")

            return response.get("result", {})

    async def close(self) -> None:
        if self._process is not None and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------

class NarrativeMcpClient:
    """Unified interface to Book Series + Writer MCP servers for the ai-novel-engine pipeline."""

    def __init__(self) -> None:
        self._book_series: _StdioSession | None = None
        self._writer: _StdioSession | None = None

        if not _is_enabled():
            logger.debug("Narrative MCP integration disabled")
            return

        bs_cmd = _parse_command("NARRATIVE_MCP_BOOK_SERIES_COMMAND")
        if bs_cmd:
            self._book_series = _StdioSession(command=bs_cmd, label="BookSeries")
        else:
            logger.warning("NARRATIVE_MCP_BOOK_SERIES_COMMAND not set — book-series tools unavailable")

        wr_cmd = _parse_command("NARRATIVE_MCP_WRITER_COMMAND")
        if wr_cmd:
            self._writer = _StdioSession(command=wr_cmd, label="Writer")
        else:
            logger.warning("NARRATIVE_MCP_WRITER_COMMAND not set — writer tools unavailable")

    @property
    def is_configured(self) -> bool:
        return _is_enabled() and (self._book_series is not None or self._writer is not None)

    # ------------------------------------------------------------------
    # Tool: track_character
    # ------------------------------------------------------------------

    async def track_character(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        *,
        book_id: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a character in the Book Series tracker.

        Args:
            name: Character name (unique key within a book/series).
            attributes: Freeform character attributes (appearance, traits, etc.).
            book_id: Optional book identifier within a series.
        """
        if self._book_series is None:
            raise RuntimeError("Book Series MCP server not configured")

        return await self._book_series.call_tool(
            "track_character",
            {"name": name, "attributes": attributes or {}, "book_id": book_id or "default"},
        )

    # ------------------------------------------------------------------
    # Tool: update_plot
    # ------------------------------------------------------------------

    async def update_plot(
        self,
        event: str,
        chapter: str | None = None,
        characters_involved: list[str] | None = None,
        *,
        book_id: str | None = None,
    ) -> dict[str, Any]:
        """Record a plot event in the Book Series tracker.

        Args:
            event: Description of the plot event.
            chapter: Chapter or section where the event occurs.
            characters_involved: List of character names involved.
            book_id: Optional book identifier.
        """
        if self._book_series is None:
            raise RuntimeError("Book Series MCP server not configured")

        return await self._book_series.call_tool(
            "update_plot",
            {
                "event": event,
                "chapter": chapter or "",
                "characters_involved": characters_involved or [],
                "book_id": book_id or "default",
            },
        )

    # ------------------------------------------------------------------
    # Tool: check_consistency
    # ------------------------------------------------------------------

    async def check_consistency(
        self,
        text: str,
        *,
        book_id: str | None = None,
        scope: str = "all",
    ) -> dict[str, Any]:
        """Check narrative consistency of a text passage.

        Uses both Book Series (plot/timeline) and Writer (character knowledge)
        servers when available, merging their results.

        Args:
            text: The narrative text to check.
            book_id: Optional book identifier.
            scope: Check scope — "all", "characters", "plot", "timeline".
        """
        results: dict[str, Any] = {"issues": [], "ok": True}

        tasks: list[tuple[str, Any]] = []

        if self._book_series is not None:
            tasks.append((
                "book_series",
                self._book_series.call_tool(
                    "check_consistency",
                    {"text": text, "book_id": book_id or "default", "scope": scope},
                ),
            ))

        if self._writer is not None:
            tasks.append((
                "writer",
                self._writer.call_tool(
                    "check_consistency",
                    {"text": text, "scope": scope},
                ),
            ))

        if not tasks:
            raise RuntimeError("No narrative MCP servers configured")

        for label, coro in tasks:
            try:
                r = await coro
                issues = r.get("issues", [])
                if issues:
                    results["issues"].extend(issues)
                    results["ok"] = False
                results[label] = r
            except Exception as exc:
                logger.warning("Consistency check failed on %s: %s", label, exc)
                results["issues"].append({"source": label, "error": str(exc)})
                results["ok"] = False

        return results

    # ------------------------------------------------------------------
    # Tool: get_world_state
    # ------------------------------------------------------------------

    async def get_world_state(self, *, book_id: str | None = None) -> dict[str, Any]:
        """Retrieve the full world state from the Book Series tracker.

        Returns characters, locations, plot events, and timeline.
        """
        if self._book_series is None:
            raise RuntimeError("Book Series MCP server not configured")

        return await self._book_series.call_tool(
            "get_world_state",
            {"book_id": book_id or "default"},
        )

    # ------------------------------------------------------------------
    # Tool: get_character_knowledge
    # ------------------------------------------------------------------

    async def get_character_knowledge(
        self,
        character_name: str,
        *,
        aspect: str | None = None,
    ) -> dict[str, Any]:
        """Query the Writer MCP server for a character's knowledge base.

        Args:
            character_name: The character to query.
            aspect: Optional aspect to focus on (e.g. "motivations", "relationships").
        """
        if self._writer is None:
            raise RuntimeError("Writer MCP server not configured")

        params: dict[str, Any] = {"character_name": character_name}
        if aspect:
            params["aspect"] = aspect

        return await self._writer.call_tool("get_character_knowledge", params)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        for session in (self._book_series, self._writer):
            if session is not None:
                try:
                    await session.close()
                except Exception:
                    logger.debug("Error closing %s session", session.label, exc_info=True)

    # ------------------------------------------------------------------
    # MCP tool definitions (for agent registry)
    # ------------------------------------------------------------------

    @staticmethod
    def tool_definitions() -> list[dict]:
        """Return MCP tool definitions for narrative integration."""
        return [
            {
                "name": "narrative_track_character",
                "description": "Create or update a character in the narrative tracker",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Character name"},
                        "attributes": {"type": "object", "description": "Character attributes"},
                        "book_id": {"type": "string", "description": "Book identifier"},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "narrative_update_plot",
                "description": "Record a plot event in the narrative tracker",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "event": {"type": "string", "description": "Plot event description"},
                        "chapter": {"type": "string", "description": "Chapter or section"},
                        "characters_involved": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Characters involved",
                        },
                        "book_id": {"type": "string"},
                    },
                    "required": ["event"],
                },
            },
            {
                "name": "narrative_check_consistency",
                "description": "Check narrative consistency of text against tracked world state and character knowledge",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Narrative text to check"},
                        "book_id": {"type": "string"},
                        "scope": {
                            "type": "string",
                            "enum": ["all", "characters", "plot", "timeline"],
                            "default": "all",
                        },
                    },
                    "required": ["text"],
                },
            },
            {
                "name": "narrative_get_world_state",
                "description": "Retrieve the full world state (characters, locations, plot, timeline)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "book_id": {"type": "string"},
                    },
                },
            },
            {
                "name": "narrative_get_character_knowledge",
                "description": "Query a character's knowledge base from the Writer server",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "character_name": {"type": "string", "description": "Character to query"},
                        "aspect": {
                            "type": "string",
                            "description": "Focus aspect (motivations, relationships, etc.)",
                        },
                    },
                    "required": ["character_name"],
                },
            },
        ]
