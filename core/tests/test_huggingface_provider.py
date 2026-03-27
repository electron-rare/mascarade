"""Tests for HuggingFaceProvider — litellm-based with OAuth token refresh."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from mascarade.config import settings
from mascarade.router.providers.huggingface import HuggingFaceProvider

HF_SETTING_NAMES = [
    "huggingface_auth_mode",
    "huggingface_api_key",
    "huggingface_base_url",
    "huggingface_model",
    "huggingface_oauth_access_token",
    "huggingface_oauth_refresh_token",
    "huggingface_oauth_client_id",
    "huggingface_oauth_client_secret",
    "huggingface_oauth_token_endpoint",
    "huggingface_oauth_expires_at",
]


@pytest.fixture(autouse=True)
def restore_hf_settings():
    snapshot = {name: getattr(settings, name) for name in HF_SETTING_NAMES}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


@pytest.mark.asyncio
async def test_huggingface_provider_uses_api_key():
    settings.huggingface_auth_mode = "api_key"
    settings.huggingface_api_key = "hf_api_key_123456789"  # noqa: S105
    settings.huggingface_base_url = "https://router.huggingface.co/v1"

    with patch("mascarade.router.providers.huggingface.litellm", new=MagicMock()):
        provider = HuggingFaceProvider()

    assert provider.is_configured is True
    # Verify token resolution returns the API key
    token = await provider._resolve_access_token()
    assert token == "hf_api_key_123456789"


@pytest.mark.asyncio
async def test_huggingface_provider_refreshes_oauth_token():
    settings.huggingface_auth_mode = "oauth_oidc"
    settings.huggingface_oauth_access_token = ""  # noqa: S105
    settings.huggingface_oauth_refresh_token = "hf_refresh_123456789"  # noqa: S105
    settings.huggingface_oauth_client_id = "hf-client-id"
    settings.huggingface_oauth_client_secret = "hf-client-secret-123456"  # noqa: S105
    settings.huggingface_oauth_token_endpoint = "https://huggingface.co/oauth/token"  # noqa: S105
    settings.huggingface_oauth_expires_at = ""

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "access_token": "hf_oauth_access_123456789",
                "refresh_token": "hf_refresh_rotated_987654321",
                "expires_in": 3600,
            }

    class _FakeHttpxClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, data, headers):
            self.last_url = url
            return _FakeResponse()

    fake_client = _FakeHttpxClient()

    with (
        patch("mascarade.router.providers.huggingface.litellm", new=MagicMock()),
        patch("mascarade.router.providers.huggingface.httpx.AsyncClient", return_value=fake_client),
    ):
        provider = HuggingFaceProvider()
        assert provider.is_configured is True
        token = await provider._resolve_access_token()

    assert token == "hf_oauth_access_123456789"
    assert settings.huggingface_oauth_access_token == "hf_oauth_access_123456789"  # noqa: S105
    assert settings.huggingface_oauth_refresh_token == "hf_refresh_rotated_987654321"  # noqa: S105
    assert settings.huggingface_oauth_expires_at
    assert fake_client.last_url == "https://huggingface.co/oauth/token"


def test_huggingface_provider_oauth_mode_is_configured_with_refresh_token_only():
    settings.huggingface_auth_mode = "oauth_oidc"
    settings.huggingface_oauth_access_token = ""  # noqa: S105
    settings.huggingface_oauth_refresh_token = "hf_refresh_123456789"  # noqa: S105
    settings.huggingface_oauth_client_id = "hf-client-id"
    settings.huggingface_oauth_client_secret = "hf-client-secret-123456"  # noqa: S105
    settings.huggingface_oauth_expires_at = _iso_utc_for_test(
        datetime.now(tz=UTC) - timedelta(seconds=5)
    )

    with patch("mascarade.router.providers.huggingface.litellm", new=MagicMock()):
        provider = HuggingFaceProvider()

    assert provider.is_configured is True


def _iso_utc_for_test(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
