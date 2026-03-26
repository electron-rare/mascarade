"""Tests for Mistral AI Studio agents integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from mascarade.agents.mistral_agents import (
    MistralRemoteAgent,
    discover_mistral_agents,
    register_mistral_agents,
)

# A valid-looking SecretStr that passes is_secret_configured
_FAKE_API_KEY = SecretStr("test-mistral-key-12345678")


def _configure_settings(mock_settings) -> None:
    mock_settings.mistral_api_key = _FAKE_API_KEY
    mock_settings.mistral_api_base = "https://api.mistral.ai/v1"
    mock_settings.mistral_agents_api_mode = "beta"
    mock_settings.mistral_agent_devstral_id = ""
    mock_settings.mistral_agent_forge_id = ""
    mock_settings.mistral_agent_tower_id = ""
    mock_settings.mistral_agent_sentinelle_id = ""


def test_mistral_remote_agent_attributes():
    agent = MistralRemoteAgent(
        name="test-agent",
        description="Test",
        system_prompt="Be helpful",
        agent_id="ag:xxx:yyy:zzz",
    )
    assert agent.name == "test-agent"
    assert agent.agent_id == "ag:xxx:yyy:zzz"
    assert agent.conversation_id is None


def test_reset_conversation():
    agent = MistralRemoteAgent(
        name="test",
        description="Test",
        system_prompt="",
        agent_id="ag:xxx",
    )
    agent.conversation_id = "conv_123"
    agent.reset_conversation()
    assert agent.conversation_id is None


@pytest.mark.asyncio
async def test_run_new_conversation():
    agent = MistralRemoteAgent(
        name="test",
        description="Test",
        system_prompt="",
        agent_id="ag:xxx",
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "conversation_id": "conv_new",
        "outputs": [{"content": "Bonjour", "role": "assistant"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    with (
        patch("mascarade.agents.mistral_agents.settings") as mock_settings,
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        _configure_settings(mock_settings)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = await agent.run("Salut")

        assert response.content == "Bonjour"
        assert response.provider == "mistral-agents"
        assert response.usage["total_tokens"] == 15
        assert agent.conversation_id == "conv_new"

        # Verify URL was for new conversation
        call_args = mock_client.post.call_args
        assert "conversations" in call_args[0][0]


@pytest.mark.asyncio
async def test_run_continue_conversation():
    agent = MistralRemoteAgent(
        name="test",
        description="Test",
        system_prompt="",
        agent_id="ag:xxx",
    )
    agent.conversation_id = "conv_existing"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "conversation_id": "conv_existing",
        "outputs": [{"content": "Suite", "role": "assistant"}],
        "usage": {},
    }

    with (
        patch("mascarade.agents.mistral_agents.settings") as mock_settings,
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        _configure_settings(mock_settings)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await agent.run("Continue")

        # Verify URL includes conversation_id
        call_args = mock_client.post.call_args
        assert "conv_existing" in call_args[0][0]


@pytest.mark.asyncio
async def test_run_no_api_key():
    agent = MistralRemoteAgent(
        name="test",
        description="Test",
        system_prompt="",
        agent_id="ag:xxx",
    )

    with patch("mascarade.agents.mistral_agents.settings") as mock_settings:
        mock_settings.mistral_api_key = SecretStr("")
        mock_settings.mistral_api_base = "https://api.mistral.ai/v1"
        mock_settings.mistral_agents_api_mode = "beta"
        with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
            await agent.run("test")


@pytest.mark.asyncio
async def test_discover_no_api_key():
    with patch("mascarade.agents.mistral_agents.settings") as mock_settings:
        mock_settings.mistral_api_key = SecretStr("")
        mock_settings.mistral_api_base = "https://api.mistral.ai/v1"
        result = await discover_mistral_agents()
        assert result == []


def test_register_default_agents():
    registry = MagicMock()

    with patch("mascarade.agents.mistral_agents.settings") as mock_settings:
        _configure_settings(mock_settings)
        register_mistral_agents(registry)

    # 4 default agents registered
    assert registry.register.call_count == 4
    names = [call[0][0].name for call in registry.register.call_args_list]
    assert "devstral-code" in names
    assert "forge" in names
    assert "tower-commercial" in names
    assert "sentinelle" in names


def test_register_default_agents_uses_configured_ids():
    registry = MagicMock()

    with patch("mascarade.agents.mistral_agents.settings") as mock_settings:
        _configure_settings(mock_settings)
        mock_settings.mistral_agent_devstral_id = "ag-dev"
        mock_settings.mistral_agent_forge_id = "ag-forge"
        mock_settings.mistral_agent_tower_id = "ag-tower"
        mock_settings.mistral_agent_sentinelle_id = "ag-sentinelle"
        register_mistral_agents(registry)

    registered = {call[0][0].name: call[0][0].agent_id for call in registry.register.call_args_list}
    assert registered["devstral-code"] == "ag-dev"
    assert registered["forge"] == "ag-forge"
    assert registered["tower-commercial"] == "ag-tower"
    assert registered["sentinelle"] == "ag-sentinelle"


def test_register_no_api_key():
    registry = MagicMock()

    with patch("mascarade.agents.mistral_agents.settings") as mock_settings:
        mock_settings.mistral_api_key = SecretStr("")
        mock_settings.mistral_api_base = "https://api.mistral.ai/v1"
        register_mistral_agents(registry)

    assert registry.register.call_count == 0
