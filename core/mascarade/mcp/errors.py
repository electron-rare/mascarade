"""MCP error hierarchy for Mascarade."""

from __future__ import annotations

from typing import Any


class McpError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        server_key: str,
        tool_name: str | None = None,
        protocol_version: str | None = None,
        transport: str = "stdio",
        latency_ms: float | None = None,
        structured_content: dict[str, Any] | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.server_key = server_key
        self.tool_name = tool_name
        self.protocol_version = protocol_version
        self.transport = transport
        self.latency_ms = latency_ms
        self.structured_content = structured_content or {}
        self.error_code = error_code


class McpServerUnavailable(McpError):
    """The target MCP server could not be started or initialized."""


class McpCallError(McpError):
    """The MCP server answered, but the requested tool call failed."""
