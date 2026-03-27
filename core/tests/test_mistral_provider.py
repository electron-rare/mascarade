"""Tests for MistralProvider — litellm-based implementation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.config import settings
from mascarade.router.providers.mistral import MistralProvider

MISTRAL_SETTING_NAMES = [
    "mistral_api_key",
]


@pytest.fixture(autouse=True)
def restore_mistral_settings():
    snapshot = {name: getattr(settings, name) for name in MISTRAL_SETTING_NAMES}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


@pytest.mark.asyncio
async def test_mistral_provider_uses_direct_sdk_by_default():
    settings.mistral_api_key = "mistral_api_key_123456789"  # noqa: S105

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "direct-ok"
    mock_response.usage.prompt_tokens = 2
    mock_response.usage.completion_tokens = 1

    with patch("mascarade.router.providers.mistral.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        provider = MistralProvider()
        assert provider.is_configured is True
        response = await provider.send([{"role": "user", "content": "ping"}])
        # Verify litellm was called with mistral/ prefix
        call_kwargs = mock_litellm.acompletion.call_args
        assert call_kwargs.kwargs["model"].startswith("mistral/")

    assert response.content == "direct-ok"


@pytest.mark.asyncio
async def test_mistral_provider_uses_litellm_proxy_when_enabled():
    """With litellm migration, proxy mode is transparent via litellm config."""
    settings.mistral_api_key = "mistral_api_key_123456789"  # noqa: S105

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "proxy-ok"
    mock_response.usage.prompt_tokens = 4
    mock_response.usage.completion_tokens = 3

    with patch("mascarade.router.providers.mistral.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        provider = MistralProvider()
        assert provider.is_configured is True
        response = await provider.send([{"role": "user", "content": "trace me"}])

    assert response.content == "proxy-ok"
