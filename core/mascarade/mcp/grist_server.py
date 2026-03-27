"""MCP server wrapper for Grist no-code database.

Exposes Grist REST API as MCP tools: documents, tables, records.

Requires env vars:
  GRIST_URL     — e.g. https://grist.lelectronrare.fr
  GRIST_API_KEY — Grist API key
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx

logger = logging.getLogger("mascarade.mcp.grist")

_DEFAULT_TIMEOUT = 30.0


class GristMcpClient:
    """MCP-compatible client for Grist."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (base_url or os.getenv("GRIST_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("GRIST_API_KEY", "")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Generic Grist API helpers
    # ------------------------------------------------------------------

    async def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        """GET request to Grist REST API."""
        if not self.is_configured:
            raise RuntimeError("Grist MCP not configured (missing GRIST_URL or GRIST_API_KEY)")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/api{endpoint}",
                headers=self._headers(),
                params=params or {},
            )
            resp.raise_for_status()
            return resp.json()

    async def _post(self, endpoint: str, data: dict) -> dict:
        """POST request to Grist REST API."""
        if not self.is_configured:
            raise RuntimeError("Grist MCP not configured (missing GRIST_URL or GRIST_API_KEY)")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api{endpoint}",
                headers=self._headers(),
                json=data,
            )
            resp.raise_for_status()
            return resp.json()

    async def _patch(self, endpoint: str, data: dict) -> dict:
        """PATCH request to Grist REST API."""
        if not self.is_configured:
            raise RuntimeError("Grist MCP not configured (missing GRIST_URL or GRIST_API_KEY)")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.patch(
                f"{self.base_url}/api{endpoint}",
                headers=self._headers(),
                json=data,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Tool: list_documents
    # ------------------------------------------------------------------

    async def list_documents(self, workspace_id: int | None = None) -> list:
        """List Grist documents, optionally filtered by workspace."""
        if workspace_id is not None:
            result = await self._get(f"/workspaces/{workspace_id}")
            return result.get("docs", result) if isinstance(result, dict) else result
        # List all workspaces and flatten docs
        orgs = await self._get("/orgs")
        all_docs = []
        if isinstance(orgs, list):
            for org in orgs:
                org_id = org.get("id")
                if org_id is None:
                    continue
                try:
                    workspaces = await self._get(f"/orgs/{org_id}/workspaces")
                    if isinstance(workspaces, list):
                        for ws in workspaces:
                            for doc in ws.get("docs", []):
                                doc["workspace"] = ws.get("name", "")
                                all_docs.append(doc)
                except httpx.HTTPError:
                    logger.warning("Failed to list workspaces for org %s", org_id)
        return all_docs

    # ------------------------------------------------------------------
    # Tool: query_table
    # ------------------------------------------------------------------

    async def query_table(
        self,
        doc_id: str,
        table_id: str,
        limit: int | None = None,
        filter: dict | None = None,
    ) -> dict:
        """Query records from a Grist table.

        Args:
            doc_id: Document ID.
            table_id: Table name/ID.
            limit: Max records to return.
            filter: Column filter dict, e.g. {"Status": ["Active"]}.
        """
        params: dict[str, object] = {}
        if limit is not None:
            params["limit"] = limit
        if filter:
            import json
            params["filter"] = json.dumps(filter)

        return await self._get(f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/records", params=params)

    # ------------------------------------------------------------------
    # Tool: add_record
    # ------------------------------------------------------------------

    async def add_record(
        self,
        doc_id: str,
        table_id: str,
        fields: dict,
    ) -> dict:
        """Add a single record to a Grist table.

        Args:
            doc_id: Document ID.
            table_id: Table name/ID.
            fields: Column-value pairs for the new record.
        """
        data = {"records": [{"fields": fields}]}
        return await self._post(f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/records", data)

    # ------------------------------------------------------------------
    # Tool: update_record
    # ------------------------------------------------------------------

    async def update_record(
        self,
        doc_id: str,
        table_id: str,
        record_id: int,
        fields: dict,
    ) -> dict:
        """Update an existing record in a Grist table.

        Args:
            doc_id: Document ID.
            table_id: Table name/ID.
            record_id: Row ID to update.
            fields: Column-value pairs to update.
        """
        data = {"records": [{"id": record_id, "fields": fields}]}
        return await self._patch(f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/records", data)

    # ------------------------------------------------------------------
    # MCP tool definitions (for registration)
    # ------------------------------------------------------------------

    @staticmethod
    def tool_definitions() -> list[dict]:
        """Return MCP tool definitions for Grist integration."""
        return [
            {
                "name": "grist_list_documents",
                "description": "List Grist documents, optionally filtered by workspace",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workspace_id": {
                            "type": "integer",
                            "description": "Optional workspace ID to filter by",
                        },
                    },
                },
            },
            {
                "name": "grist_query_table",
                "description": "Query records from a Grist table with optional filters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doc_id": {"type": "string", "description": "Grist document ID"},
                        "table_id": {"type": "string", "description": "Table name or ID"},
                        "limit": {"type": "integer", "description": "Max records to return"},
                        "filter": {
                            "type": "object",
                            "description": "Column filters, e.g. {\"Status\": [\"Active\"]}",
                        },
                    },
                    "required": ["doc_id", "table_id"],
                },
            },
            {
                "name": "grist_add_record",
                "description": "Add a new record to a Grist table",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doc_id": {"type": "string", "description": "Grist document ID"},
                        "table_id": {"type": "string", "description": "Table name or ID"},
                        "fields": {
                            "type": "object",
                            "description": "Column-value pairs for the new record",
                        },
                    },
                    "required": ["doc_id", "table_id", "fields"],
                },
            },
            {
                "name": "grist_update_record",
                "description": "Update an existing record in a Grist table",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doc_id": {"type": "string", "description": "Grist document ID"},
                        "table_id": {"type": "string", "description": "Table name or ID"},
                        "record_id": {"type": "integer", "description": "Row ID to update"},
                        "fields": {
                            "type": "object",
                            "description": "Column-value pairs to update",
                        },
                    },
                    "required": ["doc_id", "table_id", "record_id", "fields"],
                },
            },
        ]
