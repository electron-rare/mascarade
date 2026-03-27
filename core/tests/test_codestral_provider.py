"""Tests for Codestral provider (litellm-based chat + direct httpx FIM)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.router.providers.codestral import CodestralProvider


@pytest.fixture
def provider():
    with (
        patch("mascarade.router.providers.codestral.litellm", new=MagicMock()),
        patch("mascarade.router.providers.codestral.settings") as mock_settings,
    ):
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
    with (
        patch("mascarade.router.providers.codestral.litellm", new=MagicMock()),
        patch("mascarade.router.providers.codestral.settings") as mock_settings,
    ):
        mock_settings.codestral_api_key = ""
        mock_settings.codestral_timeout_seconds = 30.0
        p = CodestralProvider()
        assert not p.is_configured


@pytest.mark.asyncio
async def test_codestral_send(provider):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "def hello():\n    print('world')"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 8

    with patch("mascarade.router.providers.codestral.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        response = await provider.send(
            [{"role": "user", "content": "Write a hello function"}],
            temperature=0.0,
        )

    assert response.content == "def hello():\n    print('world')"
    assert response.provider == "codestral"


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
    mock_response = MagicMock()
    mock_response.choices = []

    with patch("mascarade.router.providers.codestral.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        with pytest.raises(RuntimeError, match="empty choices"):
            await provider.send([{"role": "user", "content": "test"}])


def test_codestral_available_models(provider):
    models = provider.available_models()
    assert isinstance(models, list)
    assert "codestral-latest" in models
    assert "codestral-2501" in models
    assert len(models) >= 2


@pytest.mark.asyncio
async def test_codestral_stream(provider):
    """Test the stream method yields content chunks via litellm."""

    async def fake_stream(*args, **kwargs):
        for text in ["hello", " world"]:
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=text))]
            )

    with patch("mascarade.router.providers.codestral.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=fake_stream())
        chunks = []
        async for chunk in provider.stream(
            [{"role": "user", "content": "hi"}],
            temperature=0.0,
        ):
            chunks.append(chunk)

    assert chunks == ["hello", " world"]
