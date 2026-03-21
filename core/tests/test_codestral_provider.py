"""Tests for Codestral provider."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mascarade.router.providers.codestral import CodestralProvider


@pytest.fixture
def provider():
    with patch.object(CodestralProvider, "is_configured", True):
        with patch("mascarade.config.settings") as mock_settings:
            mock_settings.codestral_api_key = "test-codestral-key"
            mock_settings.codestral_timeout_seconds = 30.0
            p = CodestralProvider()
            return p


def test_codestral_provider_attributes():
    assert CodestralProvider.name == "codestral"
    assert CodestralProvider.default_model == "codestral-latest"
    assert CodestralProvider.cost_per_million == (0.3, 0.9)
    assert CodestralProvider.speed_rank == 1
    assert CodestralProvider.quality_rank == 3


def test_codestral_not_configured():
    with patch("mascarade.config.settings") as mock_settings:
        mock_settings.codestral_api_key = ""
        mock_settings.codestral_timeout_seconds = 30.0
        p = CodestralProvider()
        assert not p.is_configured


@pytest.mark.asyncio
async def test_codestral_send(provider):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "def hello():\n    print('world')"}}],
        "model": "codestral-latest",
        "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
    }

    provider._client.post = AsyncMock(return_value=mock_resp)

    response = await provider.send(
        [{"role": "user", "content": "Write a hello function"}],
        temperature=0.0,
    )

    assert response.content == "def hello():\n    print('world')"
    assert response.provider == "codestral"
    assert response.usage["total_tokens"] == 18


@pytest.mark.asyncio
async def test_codestral_fim(provider):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"text": "    return a + b\n"}],
        "model": "codestral-latest",
    }

    provider._client.post = AsyncMock(return_value=mock_resp)

    result = await provider.fill_in_middle(
        prompt="def add(a, b):\n",
        suffix="\n\nresult = add(1, 2)",
        temperature=0.0,
    )

    assert result == "    return a + b\n"
    # Verify FIM endpoint was called
    call_args = provider._client.post.call_args
    assert "fim" in call_args[0][0]


@pytest.mark.asyncio
async def test_codestral_send_empty_response(provider):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [], "model": "codestral-latest"}

    provider._client.post = AsyncMock(return_value=mock_resp)

    with pytest.raises(RuntimeError, match="empty choices"):
        await provider.send([{"role": "user", "content": "test"}])
