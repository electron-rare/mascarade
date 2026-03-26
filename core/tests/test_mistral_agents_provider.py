"""Tests for the Mistral Agents router provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import SecretStr

from mascarade.router.providers.mistral_agents import MistralAgentsProvider

_FAKE_API_KEY = SecretStr("test-mistral-key-12345678")


def _configure_settings(mock_settings, *, api_mode: str = "beta") -> None:
    mock_settings.mistral_api_key = _FAKE_API_KEY
    mock_settings.mistral_api_base = "https://api.mistral.ai/v1"
    mock_settings.mistral_timeout_ms = 120000
    mock_settings.mistral_agents_api_mode = api_mode
    mock_settings.mistral_agent_sentinelle_id = "ag-sentinelle"
    mock_settings.mistral_agent_tower_id = "ag-tower"
    mock_settings.mistral_agent_forge_id = "ag-forge"
    mock_settings.mistral_agent_devstral_id = "ag-dev"


def test_mistral_agents_provider_is_configured():
    with patch("mascarade.router.providers.mistral_agents.settings") as mock_settings:
        _configure_settings(mock_settings)
        provider = MistralAgentsProvider()
        assert provider.is_configured is True
        assert "agent:sentinelle" in provider.available_models()
        assert "agent:devstral-code" in provider.available_models()


def test_mistral_agents_provider_not_configured_without_agent_ids():
    with patch("mascarade.router.providers.mistral_agents.settings") as mock_settings:
        mock_settings.mistral_api_key = _FAKE_API_KEY
        mock_settings.mistral_api_base = "https://api.mistral.ai/v1"
        mock_settings.mistral_timeout_ms = 120000
        mock_settings.mistral_agents_api_mode = "beta"
        mock_settings.mistral_agent_sentinelle_id = ""
        mock_settings.mistral_agent_tower_id = ""
        mock_settings.mistral_agent_forge_id = ""
        mock_settings.mistral_agent_devstral_id = ""
        provider = MistralAgentsProvider()
        assert provider.is_configured is False
        assert provider.available_models() == []


@pytest.mark.asyncio
async def test_mistral_agents_provider_send_beta():
    with patch("mascarade.router.providers.mistral_agents.settings") as mock_settings:
        _configure_settings(mock_settings)
        provider = MistralAgentsProvider()

        with patch.object(
            provider,
            "_call_beta",
            AsyncMock(
                return_value={
                    "conversation_id": "conv-1",
                    "outputs": [{"role": "assistant", "content": "Bonjour"}],
                    "usage": {
                        "prompt_tokens": 11,
                        "completion_tokens": 7,
                        "total_tokens": 18,
                    },
                }
            ),
        ) as call_beta:
            response = await provider.send(
                [{"role": "user", "content": "Salut"}],
                model="agent:sentinelle",
            )

    assert response.content == "Bonjour"
    assert response.model == "agent:sentinelle"
    assert response.provider == "mistral-agents"
    assert response.usage["total_tokens"] == 18
    call_beta.assert_awaited_once()


@pytest.mark.asyncio
async def test_mistral_agents_provider_fallbacks_to_deprecated():
    with patch("mascarade.router.providers.mistral_agents.settings") as mock_settings:
        _configure_settings(mock_settings)
        provider = MistralAgentsProvider()

        with (
            patch.object(
                provider,
                "_call_beta",
                AsyncMock(side_effect=httpx.TransportError("beta down")),
            ),
            patch.object(
                provider,
                "_call_deprecated",
                AsyncMock(
                    return_value={
                        "choices": [{"message": {"content": "Fallback ok"}}],
                        "usage": {
                            "prompt_tokens": 3,
                            "completion_tokens": 2,
                            "total_tokens": 5,
                        },
                    }
                ),
            ) as call_deprecated,
        ):
            response = await provider.send(
                [{"role": "user", "content": "Analyse"}],
                model="agent:forge",
            )

    assert response.content == "Fallback ok"
    assert response.model == "agent:forge"
    call_deprecated.assert_awaited_once()


@pytest.mark.asyncio
async def test_mistral_agents_provider_send_to_agent_keeps_conversation_id():
    with patch("mascarade.router.providers.mistral_agents.settings") as mock_settings:
        _configure_settings(mock_settings)
        provider = MistralAgentsProvider()

        with patch.object(
            provider,
            "_call_beta",
            AsyncMock(
                return_value={
                    "conversation_id": "conv-xyz",
                    "outputs": [{"role": "assistant", "content": "Suite"}],
                    "usage": {
                        "prompt_tokens": 2,
                        "completion_tokens": 4,
                        "total_tokens": 6,
                    },
                }
            ),
        ) as call_beta:
            response = await provider.send_to_agent(
                "tower-commercial",
                "Continue",
                conversation_id="conv-xyz",
            )

    assert response.agent_name == "tower"
    assert response.agent_id == "ag-tower"
    assert response.conversation_id == "conv-xyz"
    assert response.api_mode == "beta"
    call_beta.assert_awaited_once()
    assert call_beta.await_args.kwargs["conversation_id"] == "conv-xyz"


@pytest.mark.asyncio
async def test_mistral_agents_provider_handoff():
    with patch("mascarade.router.providers.mistral_agents.settings") as mock_settings:
        _configure_settings(mock_settings)
        provider = MistralAgentsProvider()

        with patch.object(
            provider,
            "send_to_agent",
            AsyncMock(
                side_effect=[
                    type("Resp", (), {"content": "Diagnostic", "api_mode": "beta"})(),
                    type("Resp", (), {"content": "Fix", "api_mode": "deprecated"})(),
                ]
            ),
        ) as send_to_agent:
            first, second = await provider.handoff("sentinelle", "devstral", "Incident")

    assert first.content == "Diagnostic"
    assert second.content == "Fix"
    assert send_to_agent.await_count == 2
