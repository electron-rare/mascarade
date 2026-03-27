"""Tests for GoogleProvider — litellm-based with 3-mode auth (api_key / oauth_oidc / adc)."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from mascarade.config import settings
from mascarade.router.providers.google import GoogleProvider

GOOGLE_SETTING_NAMES = [
    "google_api_key",
    "google_auth_mode",
    "google_oauth_access_token",
    "google_oauth_refresh_token",
    "google_oauth_client_id",
    "google_oauth_client_secret",
    "google_oauth_token_endpoint",
    "google_oauth_expires_at",
    "google_cloud_project",
    "google_cloud_location",
    "google_application_credentials",
    "google_model",
]


@pytest.fixture(autouse=True)
def restore_google_settings():
    snapshot = {name: getattr(settings, name) for name in GOOGLE_SETTING_NAMES}
    env_snapshot = {
        k: os.environ.get(k) for k in [
            "GEMINI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
            "VERTEXAI_PROJECT", "VERTEXAI_LOCATION",
        ]
    }
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)
    for k, v in env_snapshot.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.mark.asyncio
async def test_google_provider_uses_api_key():
    settings.google_auth_mode = "api_key"
    settings.google_api_key = "google_api_key_123456789"  # noqa: S105
    settings.google_application_credentials = ""

    with patch("mascarade.router.providers.google.litellm", new=MagicMock()):
        provider = GoogleProvider()

    assert provider.is_configured is True
    # API key should be pushed to env for litellm
    assert os.environ.get("GEMINI_API_KEY") == "google_api_key_123456789"


@pytest.mark.asyncio
async def test_google_provider_uses_oauth_credentials():
    settings.google_auth_mode = "oauth_oidc"
    settings.google_oauth_access_token = "ya29.oauth_access_123456789"  # noqa: S105
    settings.google_oauth_refresh_token = "1//refresh-token-123456789"  # noqa: S105
    settings.google_oauth_client_id = "google-client-id"
    settings.google_oauth_client_secret = "google-client-secret-123456"  # noqa: S105
    settings.google_oauth_expires_at = (
        (datetime.now(tz=UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    )
    settings.google_application_credentials = ""

    with patch("mascarade.router.providers.google.litellm", new=MagicMock()):
        provider = GoogleProvider()

    assert provider.is_configured is True


@pytest.mark.asyncio
async def test_google_provider_refreshes_oauth_token():
    settings.google_auth_mode = "oauth_oidc"
    settings.google_oauth_access_token = ""  # noqa: S105
    settings.google_oauth_refresh_token = "1//refresh-token-123456789"  # noqa: S105
    settings.google_oauth_client_id = "google-client-id"
    settings.google_oauth_client_secret = "google-client-secret-123456"  # noqa: S105
    settings.google_oauth_token_endpoint = "https://oauth2.googleapis.com/token"  # noqa: S105
    settings.google_application_credentials = ""

    def fake_refresh(self, _request):
        self.token = "ya29.refreshed_access_987654321"  # noqa: S105
        self.expiry = datetime.now(tz=UTC) + timedelta(hours=1)

    with (
        patch("mascarade.router.providers.google.litellm", new=MagicMock()),
        patch(
            "mascarade.router.providers.google.Credentials.refresh",
            fake_refresh,
        ),
    ):
        provider = GoogleProvider()
        # Trigger OAuth resolution which should refresh the token
        provider._ensure_oauth_env()

    assert settings.google_oauth_access_token == "ya29.refreshed_access_987654321"  # noqa: S105
    assert settings.google_oauth_expires_at


def test_google_provider_adc_mode_requires_project_and_credentials_path():
    settings.google_auth_mode = "adc"
    settings.google_cloud_project = "mascarade-test"
    settings.google_application_credentials = "/tmp/google-creds.json"  # noqa: S108

    with patch("mascarade.router.providers.google.litellm", new=MagicMock()):
        provider = GoogleProvider()

    assert provider.is_configured is True
