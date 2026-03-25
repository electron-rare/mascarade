"""MCP server wrapper for n8n workflow automation.

Exposes n8n workflows as MCP tools, allowing mascarade agents
to trigger, list, and query n8n workflow executions.

Requires env vars:
  N8N_BASE_URL  — e.g. http://n8n.saillant.cc or http://localhost:5678
  N8N_API_KEY   — n8n API key for authentication
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("mascarade.mcp.n8n")

_DEFAULT_TIMEOUT = 30.0


class N8nMcpClient:
    """MCP-compatible client for n8n workflow automation."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (base_url or os.getenv("N8N_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("N8N_API_KEY", "")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "X-N8N-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Tool: list_workflows
    # ------------------------------------------------------------------

    async def list_workflows(self, limit: int = 50) -> list[dict]:
        """List available n8n workflows.

        Returns list of {id, name, active, tags}.
        """
        if not self.is_configured:
            return []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/workflows",
                headers=self._headers(),
                params={"limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()

        workflows = data.get("data", data) if isinstance(data, dict) else data
        return [
            {
                "id": w.get("id"),
                "name": w.get("name", ""),
                "active": w.get("active", False),
                "tags": [t.get("name", "") for t in w.get("tags", [])],
            }
            for w in (workflows if isinstance(workflows, list) else [])
        ]

    # ------------------------------------------------------------------
    # Tool: execute_workflow
    # ------------------------------------------------------------------

    async def execute_workflow(
        self,
        workflow_id: str,
        data: dict | None = None,
    ) -> dict:
        """Trigger a n8n workflow execution via webhook or API.

        Returns {executionId, status, data}.
        """
        if not self.is_configured:
            raise RuntimeError("n8n MCP not configured (missing N8N_BASE_URL or N8N_API_KEY)")

        payload = data or {}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/workflows/{workflow_id}/run",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Tool: get_execution
    # ------------------------------------------------------------------

    async def get_execution(self, execution_id: str) -> dict:
        """Get the status and result of a workflow execution.

        Returns {id, finished, status, data, startedAt, stoppedAt}.
        """
        if not self.is_configured:
            raise RuntimeError("n8n MCP not configured")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/executions/{execution_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Tool: list_executions
    # ------------------------------------------------------------------

    async def list_executions(
        self,
        workflow_id: str | None = None,
        limit: int = 20,
        status: str | None = None,
    ) -> list[dict]:
        """List recent workflow executions.

        Args:
            workflow_id: Filter by workflow ID.
            limit: Max results.
            status: Filter by status (success, error, waiting).
        """
        if not self.is_configured:
            return []

        params: dict[str, object] = {"limit": limit}
        if workflow_id:
            params["workflowId"] = workflow_id
        if status:
            params["status"] = status

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/executions",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        executions = data.get("data", data) if isinstance(data, dict) else data
        return executions if isinstance(executions, list) else []

    # ------------------------------------------------------------------
    # MCP tool definitions (for registration)
    # ------------------------------------------------------------------

    @staticmethod
    def tool_definitions() -> list[dict]:
        """Return MCP tool definitions for n8n integration."""
        return [
            {
                "name": "n8n_list_workflows",
                "description": "List available n8n automation workflows",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 50},
                    },
                },
            },
            {
                "name": "n8n_execute_workflow",
                "description": "Trigger a n8n workflow execution",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string", "description": "n8n workflow ID"},
                        "data": {"type": "object", "description": "Input data for the workflow"},
                    },
                    "required": ["workflow_id"],
                },
            },
            {
                "name": "n8n_get_execution",
                "description": "Get status and result of a workflow execution",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "execution_id": {"type": "string"},
                    },
                    "required": ["execution_id"],
                },
            },
            {
                "name": "n8n_list_executions",
                "description": "List recent workflow executions with optional filters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 20},
                        "status": {"type": "string", "enum": ["success", "error", "waiting"]},
                    },
                },
            },
        ]
