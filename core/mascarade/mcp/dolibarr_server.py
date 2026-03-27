"""MCP server wrapper for Dolibarr ERP/CRM.

Exposes Dolibarr REST API as MCP tools: quotes, invoices, contacts, tasks.

Requires env vars:
  DOLIBARR_URL     — e.g. https://dolibarr.lelectronrare.fr
  DOLIBARR_API_KEY — Dolibarr API token (DOLAPIKEY)
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx

logger = logging.getLogger("mascarade.mcp.dolibarr")

_DEFAULT_TIMEOUT = 30.0


class DolibarrMcpClient:
    """MCP-compatible client for Dolibarr ERP/CRM."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (base_url or os.getenv("DOLIBARR_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("DOLIBARR_API_KEY", "")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "DOLAPIKEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Generic Dolibarr API helpers
    # ------------------------------------------------------------------

    async def _get(self, endpoint: str, params: dict | None = None) -> list | dict:
        """GET request to Dolibarr REST API."""
        if not self.is_configured:
            raise RuntimeError("Dolibarr MCP not configured (missing DOLIBARR_URL or DOLIBARR_API_KEY)")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/api/index.php{endpoint}",
                headers=self._headers(),
                params=params or {},
            )
            resp.raise_for_status()
            return resp.json()

    async def _post(self, endpoint: str, data: dict) -> dict:
        """POST request to Dolibarr REST API."""
        if not self.is_configured:
            raise RuntimeError("Dolibarr MCP not configured (missing DOLIBARR_URL or DOLIBARR_API_KEY)")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/index.php{endpoint}",
                headers=self._headers(),
                json=data,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Tool: list_quotes (propositions commerciales)
    # ------------------------------------------------------------------

    async def list_quotes(self, limit: int = 20) -> list:
        """List recent commercial proposals (devis)."""
        return await self._get("/proposals", params={"limit": limit, "sortfield": "t.datep", "sortorder": "DESC"})

    # ------------------------------------------------------------------
    # Tool: create_quote
    # ------------------------------------------------------------------

    async def create_quote(
        self,
        socid: int,
        lines: list[dict],
        **extra: object,
    ) -> dict:
        """Create a new commercial proposal.

        Args:
            socid: Third-party (tiers) ID.
            lines: List of {desc, qty, subprice, tva_tx}.
        """
        doc = {
            "socid": socid,
            "lines": [
                {
                    "desc": line.get("desc", ""),
                    "qty": line.get("qty", 1),
                    "subprice": line.get("subprice", 0),
                    "tva_tx": line.get("tva_tx", 20.0),
                }
                for line in lines
            ],
            **extra,
        }
        return await self._post("/proposals", doc)

    # ------------------------------------------------------------------
    # Tool: list_invoices
    # ------------------------------------------------------------------

    async def list_invoices(self, limit: int = 20) -> list:
        """List recent invoices (factures)."""
        return await self._get("/invoices", params={"limit": limit, "sortfield": "t.datef", "sortorder": "DESC"})

    # ------------------------------------------------------------------
    # Tool: create_invoice
    # ------------------------------------------------------------------

    async def create_invoice(
        self,
        socid: int,
        lines: list[dict],
        **extra: object,
    ) -> dict:
        """Create a new invoice.

        Args:
            socid: Third-party (tiers) ID.
            lines: List of {desc, qty, subprice, tva_tx}.
        """
        doc = {
            "socid": socid,
            "lines": [
                {
                    "desc": line.get("desc", ""),
                    "qty": line.get("qty", 1),
                    "subprice": line.get("subprice", 0),
                    "tva_tx": line.get("tva_tx", 20.0),
                }
                for line in lines
            ],
            **extra,
        }
        return await self._post("/invoices", doc)

    # ------------------------------------------------------------------
    # Tool: search_contacts (tiers / thirdparties)
    # ------------------------------------------------------------------

    async def search_contacts(self, query: str, limit: int = 20) -> list:
        """Search third-parties (tiers) by name."""
        return await self._get(
            "/thirdparties",
            params={"sortfield": "t.nom", "sortorder": "ASC", "limit": limit, "sqlfilters": f"(t.nom:like:'%{query}%')"},
        )

    # ------------------------------------------------------------------
    # Tool: list_tasks
    # ------------------------------------------------------------------

    async def list_tasks(self, limit: int = 20) -> list:
        """List recent tasks (projet tasks)."""
        return await self._get("/tasks", params={"limit": limit, "sortfield": "t.dateo", "sortorder": "DESC"})

    # ------------------------------------------------------------------
    # MCP tool definitions (for registration)
    # ------------------------------------------------------------------

    @staticmethod
    def tool_definitions() -> list[dict]:
        """Return MCP tool definitions for Dolibarr integration."""
        return [
            {
                "name": "dolibarr_list_quotes",
                "description": "List recent commercial proposals (devis) from Dolibarr",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20, "description": "Max results to return"},
                    },
                },
            },
            {
                "name": "dolibarr_create_quote",
                "description": "Create a new commercial proposal (devis) in Dolibarr",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "socid": {"type": "integer", "description": "Third-party (tiers) ID"},
                        "lines": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "desc": {"type": "string", "description": "Line description"},
                                    "qty": {"type": "number", "default": 1},
                                    "subprice": {"type": "number", "description": "Unit price HT"},
                                    "tva_tx": {"type": "number", "default": 20.0, "description": "VAT rate (%)"},
                                },
                                "required": ["desc", "subprice"],
                            },
                            "description": "Invoice lines",
                        },
                    },
                    "required": ["socid", "lines"],
                },
            },
            {
                "name": "dolibarr_list_invoices",
                "description": "List recent invoices (factures) from Dolibarr",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20, "description": "Max results to return"},
                    },
                },
            },
            {
                "name": "dolibarr_create_invoice",
                "description": "Create a new invoice (facture) in Dolibarr",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "socid": {"type": "integer", "description": "Third-party (tiers) ID"},
                        "lines": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "desc": {"type": "string", "description": "Line description"},
                                    "qty": {"type": "number", "default": 1},
                                    "subprice": {"type": "number", "description": "Unit price HT"},
                                    "tva_tx": {"type": "number", "default": 20.0, "description": "VAT rate (%)"},
                                },
                                "required": ["desc", "subprice"],
                            },
                            "description": "Invoice lines",
                        },
                    },
                    "required": ["socid", "lines"],
                },
            },
            {
                "name": "dolibarr_search_contacts",
                "description": "Search third-parties (tiers/contacts) in Dolibarr by name",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (name)"},
                        "limit": {"type": "integer", "default": 20},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "dolibarr_list_tasks",
                "description": "List recent project tasks from Dolibarr",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20, "description": "Max results to return"},
                    },
                },
            },
        ]
