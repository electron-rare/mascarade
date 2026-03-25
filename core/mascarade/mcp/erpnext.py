"""MCP server wrapper for ERPNext / Frappe CRM.

Exposes Frappe REST API as MCP tools for CRM operations:
leads, quotations, invoices, and sales orders.

Requires env vars:
  FRAPPE_URL       — e.g. https://erp.lelectronrare.fr
  FRAPPE_API_KEY   — Frappe API key
  FRAPPE_API_SECRET — Frappe API secret
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx

logger = logging.getLogger("mascarade.mcp.erpnext")

_DEFAULT_TIMEOUT = 30.0


class ERPNextMcpClient:
    """MCP-compatible client for ERPNext / Frappe CRM."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (base_url or os.getenv("FRAPPE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("FRAPPE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("FRAPPE_API_SECRET", "")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.api_secret)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Generic Frappe API helpers
    # ------------------------------------------------------------------

    async def _get_list(
        self,
        doctype: str,
        fields: list[str] | None = None,
        filters: dict | None = None,
        limit: int = 20,
        order_by: str = "modified desc",
    ) -> list[dict]:
        """Fetch a list of documents from Frappe."""
        if not self.is_configured:
            return []

        params: dict[str, object] = {
            "doctype": doctype,
            "fields": str(fields or ["name", "modified"]),
            "limit_page_length": limit,
            "order_by": order_by,
        }
        if filters:
            params["filters"] = str(filters)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/api/resource/{quote(doctype)}",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("data", [])

    async def _get_doc(self, doctype: str, name: str) -> dict:
        """Fetch a single document."""
        if not self.is_configured:
            raise RuntimeError("ERPNext MCP not configured")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/api/resource/{quote(doctype)}/{quote(name)}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("data", data)

    async def _create_doc(self, doctype: str, doc: dict) -> dict:
        """Create a new document."""
        if not self.is_configured:
            raise RuntimeError("ERPNext MCP not configured")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/resource/{quote(doctype)}",
                headers=self._headers(),
                json=doc,
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("data", data)

    async def _update_doc(self, doctype: str, name: str, updates: dict) -> dict:
        """Update an existing document."""
        if not self.is_configured:
            raise RuntimeError("ERPNext MCP not configured")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.put(
                f"{self.base_url}/api/resource/{quote(doctype)}/{quote(name)}",
                headers=self._headers(),
                json=updates,
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("data", data)

    # ------------------------------------------------------------------
    # Tool: list_leads
    # ------------------------------------------------------------------

    async def list_leads(self, limit: int = 20, status: str | None = None) -> list[dict]:
        """List CRM leads with optional status filter."""
        filters = {"status": status} if status else None
        return await self._get_list(
            "CRM Lead",
            fields=["name", "lead_name", "email_id", "status", "source", "modified"],
            filters=filters,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Tool: get_lead
    # ------------------------------------------------------------------

    async def get_lead(self, name: str) -> dict:
        """Get a single CRM lead by name."""
        return await self._get_doc("CRM Lead", name)

    # ------------------------------------------------------------------
    # Tool: create_lead
    # ------------------------------------------------------------------

    async def create_lead(
        self,
        lead_name: str,
        email: str,
        source: str = "Website",
        **extra: object,
    ) -> dict:
        """Create a new CRM lead."""
        doc = {
            "doctype": "CRM Lead",
            "lead_name": lead_name,
            "email_id": email,
            "source": source,
            **extra,
        }
        return await self._create_doc("CRM Lead", doc)

    # ------------------------------------------------------------------
    # Tool: list_quotations
    # ------------------------------------------------------------------

    async def list_quotations(self, limit: int = 20) -> list[dict]:
        """List sales quotations."""
        return await self._get_list(
            "Quotation",
            fields=["name", "party_name", "grand_total", "status", "transaction_date"],
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Tool: create_quotation
    # ------------------------------------------------------------------

    async def create_quotation(
        self,
        party_name: str,
        items: list[dict],
        **extra: object,
    ) -> dict:
        """Create a sales quotation.

        Args:
            party_name: Customer name.
            items: List of {item_code, qty, rate}.
        """
        doc = {
            "doctype": "Quotation",
            "quotation_to": "Customer",
            "party_name": party_name,
            "items": [
                {
                    "item_code": item.get("item_code", ""),
                    "qty": item.get("qty", 1),
                    "rate": item.get("rate", 0),
                }
                for item in items
            ],
            **extra,
        }
        return await self._create_doc("Quotation", doc)

    # ------------------------------------------------------------------
    # Tool: list_invoices
    # ------------------------------------------------------------------

    async def list_invoices(self, limit: int = 20) -> list[dict]:
        """List sales invoices."""
        return await self._get_list(
            "Sales Invoice",
            fields=["name", "customer_name", "grand_total", "status", "posting_date"],
            limit=limit,
        )

    # ------------------------------------------------------------------
    # MCP tool definitions (for registration)
    # ------------------------------------------------------------------

    @staticmethod
    def tool_definitions() -> list[dict]:
        """Return MCP tool definitions for ERPNext integration."""
        return [
            {
                "name": "erpnext_list_leads",
                "description": "List CRM leads from ERPNext",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20},
                        "status": {"type": "string", "description": "Filter by lead status"},
                    },
                },
            },
            {
                "name": "erpnext_get_lead",
                "description": "Get details of a specific CRM lead",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Lead ID (e.g. CRM-LEAD-2026-00001)"},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "erpnext_create_lead",
                "description": "Create a new CRM lead in ERPNext",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "lead_name": {"type": "string"},
                        "email": {"type": "string", "format": "email"},
                        "source": {"type": "string", "default": "Website"},
                    },
                    "required": ["lead_name", "email"],
                },
            },
            {
                "name": "erpnext_list_quotations",
                "description": "List sales quotations from ERPNext",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20},
                    },
                },
            },
            {
                "name": "erpnext_create_quotation",
                "description": "Create a sales quotation in ERPNext",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "party_name": {"type": "string"},
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "item_code": {"type": "string"},
                                    "qty": {"type": "number"},
                                    "rate": {"type": "number"},
                                },
                                "required": ["item_code"],
                            },
                        },
                    },
                    "required": ["party_name", "items"],
                },
            },
            {
                "name": "erpnext_list_invoices",
                "description": "List sales invoices from ERPNext",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20},
                    },
                },
            },
        ]
