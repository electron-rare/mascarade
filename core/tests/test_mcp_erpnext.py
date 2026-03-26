"""Tests for ERPNext MCP client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.mcp.erpnext import ERPNextMcpClient


@pytest.fixture
def client():
    return ERPNextMcpClient(
        base_url="https://erp.test.fr",
        api_key="abc123",
        api_secret="secret456",
    )


@pytest.fixture
def unconfigured_client():
    return ERPNextMcpClient(base_url="", api_key="", api_secret="")


def _mock_httpx_response(data):
    resp = MagicMock()
    resp.json.return_value = {"data": data}
    resp.raise_for_status = MagicMock()
    return resp


def _patch_httpx(method="get", response_data=None):
    mock_instance = AsyncMock()
    setattr(
        mock_instance, method, AsyncMock(return_value=_mock_httpx_response(response_data or []))
    )
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    return patch("mascarade.mcp.erpnext.httpx.AsyncClient", return_value=mock_instance)


class TestConfiguration:
    def test_is_configured(self, client):
        assert client.is_configured is True

    def test_not_configured_when_empty(self, unconfigured_client):
        assert unconfigured_client.is_configured is False

    def test_headers_include_token(self, client):
        headers = client._headers()
        assert "token abc123:secret456" in headers["Authorization"]


class TestListLeads:
    @pytest.mark.asyncio
    async def test_returns_leads(self, client):
        leads = [
            {"name": "CRM-LEAD-001", "lead_name": "Alice", "status": "Open"},
            {"name": "CRM-LEAD-002", "lead_name": "Bob", "status": "Replied"},
        ]
        with _patch_httpx("get", leads):
            result = await client.list_leads()

        assert len(result) == 2
        assert result[0]["lead_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_returns_empty_when_unconfigured(self, unconfigured_client):
        result = await unconfigured_client.list_leads()
        assert result == []


class TestGetLead:
    @pytest.mark.asyncio
    async def test_gets_lead(self, client):
        lead = {"name": "CRM-LEAD-001", "lead_name": "Alice", "email_id": "alice@test.com"}
        with _patch_httpx("get", lead):
            result = await client.get_lead("CRM-LEAD-001")
        assert result["email_id"] == "alice@test.com"

    @pytest.mark.asyncio
    async def test_raises_when_unconfigured(self, unconfigured_client):
        with pytest.raises(RuntimeError, match="not configured"):
            await unconfigured_client.get_lead("CRM-LEAD-001")


class TestCreateLead:
    @pytest.mark.asyncio
    async def test_creates_lead(self, client):
        created = {"name": "CRM-LEAD-003", "lead_name": "Charlie", "email_id": "charlie@test.com"}
        with _patch_httpx("post", created):
            result = await client.create_lead("Charlie", "charlie@test.com")
        assert result["name"] == "CRM-LEAD-003"


class TestListQuotations:
    @pytest.mark.asyncio
    async def test_returns_quotations(self, client):
        quotations = [{"name": "QTN-001", "party_name": "Alice", "grand_total": 1550}]
        with _patch_httpx("get", quotations):
            result = await client.list_quotations()
        assert len(result) == 1
        assert result[0]["grand_total"] == 1550


class TestCreateQuotation:
    @pytest.mark.asyncio
    async def test_creates_quotation(self, client):
        created = {"name": "QTN-002", "party_name": "Bob"}
        with _patch_httpx("post", created):
            result = await client.create_quotation(
                "Bob",
                [{"item_code": "FORMATION-KICAD", "qty": 1, "rate": 1550}],
            )
        assert result["name"] == "QTN-002"


class TestListInvoices:
    @pytest.mark.asyncio
    async def test_returns_invoices(self, client):
        invoices = [{"name": "SINV-001", "customer_name": "Alice", "grand_total": 775}]
        with _patch_httpx("get", invoices):
            result = await client.list_invoices()
        assert len(result) == 1


class TestToolDefinitions:
    def test_returns_6_tools(self):
        tools = ERPNextMcpClient.tool_definitions()
        assert len(tools) == 6
        names = [t["name"] for t in tools]
        assert "erpnext_list_leads" in names
        assert "erpnext_create_lead" in names
        assert "erpnext_list_quotations" in names
        assert "erpnext_create_quotation" in names
        assert "erpnext_list_invoices" in names
