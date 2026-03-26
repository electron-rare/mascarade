"""Outline MCP client — search and retrieve docs from Outline wiki."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("mascarade.mcp.outline")

_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class OutlineMcpClient:
    """Thin async client for Outline REST API.

    Tools:
    - ``search``: full-text search across all collections
    - ``get_document``: fetch a document by id or URL
    - ``list_collections``: list available collections
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """Search documents by full-text query."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base}/api/documents.search",
                headers=self._headers,
                json={"query": query, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("data", [])
        return [
            {
                "id": r.get("document", {}).get("id"),
                "title": r.get("document", {}).get("title"),
                "url": r.get("document", {}).get("url"),
                "snippet": r.get("context", ""),
                "collection": r.get("document", {}).get("collectionId"),
            }
            for r in results
        ]

    async def get_document(self, document_id: str) -> dict[str, Any]:
        """Fetch full document content by id."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base}/api/documents.info",
                headers=self._headers,
                json={"id": document_id},
            )
            resp.raise_for_status()
            data = resp.json()

        doc = data.get("data", {})
        return {
            "id": doc.get("id"),
            "title": doc.get("title"),
            "text": doc.get("text", ""),
            "url": doc.get("url"),
            "updatedAt": doc.get("updatedAt"),
            "collection": doc.get("collectionId"),
        }

    async def list_collections(self) -> list[dict[str, Any]]:
        """List all accessible collections."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base}/api/collections.list",
                headers=self._headers,
                json={"limit": 50},
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            {"id": c.get("id"), "name": c.get("name"), "description": c.get("description")}
            for c in data.get("data", [])
        ]


def get_client() -> OutlineMcpClient | None:
    """Return a configured client if OUTLINE_URL and OUTLINE_API_KEY are set."""
    url = os.getenv("OUTLINE_URL", "")
    key = os.getenv("OUTLINE_API_KEY", "")
    if not url or not key:
        return None
    return OutlineMcpClient(url, key)
