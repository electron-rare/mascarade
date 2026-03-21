"""Tests for Mistral AI Studio agents integration."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import SecretStr

from mascarade.agents.mistral_agents import (
    MistralRemoteAgent,
    discover_mistral_agents,
    register_mistral_agents,
)
from mascarade.router.router import Strategy

# A valid-looking SecretStr that passes is_secret_configured
_FAKE_API_KEY = SecretStr("test-mistral-key-12345678")


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

    with patch("mascarade.agents.mistral_agents.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_settings.mistral_api_key = _FAKE_API_KEY
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

    with patch("mascarade.agents.mistral_agents.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_settings.mistral_api_key = _FAKE_API_KEY
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = await agent.run("Continue")

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
        with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
            await agent.run("test")


@pytest.mark.asyncio
async def test_discover_no_api_key():
    with patch("mascarade.agents.mistral_agents.settings") as mock_settings:
        mock_settings.mistral_api_key = SecretStr("")
        result = await discover_mistral_agents()
        assert result == []


def test_register_default_agents():
    registry = MagicMock()

    with patch("mascarade.agents.mistral_agents.settings") as mock_settings:
        mock_settings.mistral_api_key = _FAKE_API_KEY
        register_mistral_agents(registry)

    # 4 default agents registered
    assert registry.register.call_count == 4
    names = [call[0][0].name for call in registry.register.call_args_list]
    assert "devstral-code" in names
    assert "forge" in names
    assert "tower-commercial" in names
    assert "sentinelle" in names


def test_register_no_api_key():
    registry = MagicMock()

    with patch("mascarade.agents.mistral_agents.settings") as mock_settings:
        mock_settings.mistral_api_key = SecretStr("")
        register_mistral_agents(registry)

    assert registry.register.call_count == 0
