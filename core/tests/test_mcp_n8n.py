"""Tests for n8n MCP client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.mcp.n8n import N8nMcpClient


@pytest.fixture
def client():
    return N8nMcpClient(base_url="http://n8n.test:5678", api_key="test-key")


@pytest.fixture
def unconfigured_client():
    return N8nMcpClient(base_url="", api_key="")


class TestConfiguration:
    def test_is_configured(self, client):
        assert client.is_configured is True

    def test_not_configured_when_empty(self, unconfigured_client):
        assert unconfigured_client.is_configured is False

    def test_headers_include_api_key(self, client):
        headers = client._headers()
        assert headers["X-N8N-API-KEY"] == "test-key"


class TestListWorkflows:
    @pytest.mark.asyncio
    async def test_returns_workflows(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "1", "name": "Lead Processing", "active": True, "tags": [{"name": "crm"}]},
                {"id": "2", "name": "Backup", "active": False, "tags": []},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("mascarade.mcp.n8n.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_instance

            result = await client.list_workflows()

        assert len(result) == 2
        assert result[0]["name"] == "Lead Processing"
        assert result[0]["active"] is True
        assert result[0]["tags"] == ["crm"]

    @pytest.mark.asyncio
    async def test_returns_empty_when_unconfigured(self, unconfigured_client):
        result = await unconfigured_client.list_workflows()
        assert result == []


class TestExecuteWorkflow:
    @pytest.mark.asyncio
    async def test_executes_workflow(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"executionId": "exec-123", "status": "running"}
        mock_response.raise_for_status = MagicMock()

        with patch("mascarade.mcp.n8n.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_instance

            result = await client.execute_workflow("wf-1", data={"lead_id": "L001"})

        assert result["executionId"] == "exec-123"

    @pytest.mark.asyncio
    async def test_raises_when_unconfigured(self, unconfigured_client):
        with pytest.raises(RuntimeError, match="not configured"):
            await unconfigured_client.execute_workflow("wf-1")


class TestGetExecution:
    @pytest.mark.asyncio
    async def test_gets_execution(self, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "exec-123",
            "finished": True,
            "status": "success",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("mascarade.mcp.n8n.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_instance

            result = await client.get_execution("exec-123")

        assert result["finished"] is True


class TestToolDefinitions:
    def test_returns_4_tools(self):
        tools = N8nMcpClient.tool_definitions()
        assert len(tools) == 4
        names = [t["name"] for t in tools]
        assert "n8n_list_workflows" in names
        assert "n8n_execute_workflow" in names
        assert "n8n_get_execution" in names
        assert "n8n_list_executions" in names
