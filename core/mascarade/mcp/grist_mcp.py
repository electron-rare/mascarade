"""Grist MCP client — spreadsheet database CRUD, SQL queries, table management.

Grist instance: grist.saillant.cc (Keycloak OIDC), API key auth.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from mascarade.config import settings, secret_value

logger = logging.getLogger("mascarade.mcp.grist")

_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


class GristMcpClient:
    """Async client for the Grist REST API.

    Tools:
    - ``list_documents``: list all docs in an org
    - ``list_tables``: list tables in a document
    - ``query_table``: read records from a table (with optional filters)
    - ``add_records``: add rows to a table
    - ``update_records``: update existing rows
    - ``sql_query``: run raw SQL on a document
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # ── Documents ─────────────────────────────────────────────────

    async def list_documents(self, org_id: int | str = "current") -> list[dict[str, Any]]:
        """List all documents in an org (default: current org)."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base}/api/orgs/{org_id}/workspaces",
                headers=self._headers,
            )
            resp.raise_for_status()
            workspaces = resp.json()

        docs = []
        for ws in workspaces:
            ws_name = ws.get("name", "")
            for doc in ws.get("docs", []):
                docs.append({
                    "id": doc.get("id"),
                    "name": doc.get("name"),
                    "workspace": ws_name,
                    "workspace_id": ws.get("id"),
                    "is_pinned": doc.get("isPinned", False),
                    "updated_at": doc.get("updatedAt"),
                })
        return docs

    # ── Tables ────────────────────────────────────────────────────

    async def list_tables(self, doc_id: str) -> list[dict[str, Any]]:
        """List all tables in a document."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base}/api/docs/{doc_id}/tables",
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            {"id": t.get("id"), "fields": t.get("fields", {})}
            for t in data.get("tables", [])
        ]

    # ── Records ───────────────────────────────────────────────────

    async def query_table(
        self,
        doc_id: str,
        table_id: str,
        *,
        filters: dict[str, list[Any]] | None = None,
        limit: int | None = None,
        sort: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read records from a table with optional column filters.

        ``filters``: ``{"column": [value1, value2]}`` — Grist filter format.
        ``sort``: column name, prefix with ``-`` for descending.
        """
        params: dict[str, Any] = {}
        if filters:
            import json
            params["filter"] = json.dumps(filters)
        if limit:
            params["limit"] = limit
        if sort:
            params["sort"] = sort

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base}/api/docs/{doc_id}/tables/{table_id}/records",
                headers=self._headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            {"id": r.get("id"), **r.get("fields", {})}
            for r in data.get("records", [])
        ]

    async def add_records(
        self, doc_id: str, table_id: str, records: list[dict[str, Any]]
    ) -> list[int]:
        """Add rows to a table. Each record is a dict of column→value.

        Returns list of new row IDs.
        """
        payload = {"records": [{"fields": r} for r in records]}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base}/api/docs/{doc_id}/tables/{table_id}/records",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        return [r.get("id") for r in data.get("records", [])]

    async def update_records(
        self, doc_id: str, table_id: str, records: list[dict[str, Any]]
    ) -> bool:
        """Update existing rows. Each record must have ``id`` + field updates.

        Example: ``[{"id": 1, "status": "done"}, ...]``
        """
        payload = {
            "records": [
                {"id": r.pop("id"), "fields": r} if "id" in r else {"fields": r}
                for r in [dict(rec) for rec in records]
            ]
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.patch(
                f"{self._base}/api/docs/{doc_id}/tables/{table_id}/records",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
        return True

    # ── SQL ────────────────────────────────────────────────────────

    async def sql_query(
        self, doc_id: str, sql: str, *, timeout: float = 30.0
    ) -> dict[str, Any]:
        """Run a raw SQL query against a Grist document.

        Returns ``{"records": [...], "columns": [...]}``.
        """
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=5.0)) as client:
            resp = await client.get(
                f"{self._base}/api/docs/{doc_id}/sql",
                headers=self._headers,
                params={"q": sql},
            )
            resp.raise_for_status()
            return resp.json()

    # ── Table creation ────────────────────────────────────────────

    async def create_table(
        self, doc_id: str, table_id: str, columns: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Create a new table in a document.

        ``columns``: ``[{"id": "col_name", "fields": {"type": "Text", "label": "Col Name"}}, ...]``
        """
        payload = {"tables": [{"id": table_id, "columns": columns}]}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base}/api/docs/{doc_id}/tables",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Document creation ─────────────────────────────────────────

    async def create_document(
        self, workspace_id: int, name: str, *, pinned: bool = True
    ) -> dict[str, Any]:
        """Create a new document in a workspace."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base}/api/workspaces/{workspace_id}/docs",
                headers=self._headers,
                json={"name": name, "isPinned": pinned},
            )
            resp.raise_for_status()
            # Returns the new doc ID as a plain string
            doc_id = resp.text.strip().strip('"')
            return {"id": doc_id, "name": name}


def get_client() -> GristMcpClient | None:
    """Return a configured Grist client if enabled and API key is set."""
    if not settings.grist_enabled:
        return None
    api_key = secret_value(settings.grist_api_key)
    if not api_key:
        logger.warning("GRIST_ENABLED=true but GRIST_API_KEY is empty")
        return None
    return GristMcpClient(settings.grist_api_url, api_key)
