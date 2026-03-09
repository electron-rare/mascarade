from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


class _FakeGenAIClient:
    created: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.__class__.created.append(kwargs)


@pytest.mark.asyncio
async def test_google_provider_uses_api_key(monkeypatch):
    settings.google_auth_mode = "api_key"
    settings.google_api_key = "google_api_key_123456789"  # noqa: S105
    _FakeGenAIClient.created.clear()
    monkeypatch.setattr(
        "mascarade.router.providers.google.genai.Client",
        _FakeGenAIClient,
    )

    provider = GoogleProvider()

    assert provider.is_configured is True
    client = provider._ensure_client()
    assert client.kwargs["api_key"] == "google_api_key_123456789"  # noqa: S105


@pytest.mark.asyncio
async def test_google_provider_uses_oauth_credentials(monkeypatch):
    settings.google_auth_mode = "oauth_oidc"
    settings.google_oauth_access_token = "ya29.oauth_access_123456789"  # noqa: S105
    settings.google_oauth_refresh_token = "1//refresh-token-123456789"  # noqa: S105
    settings.google_oauth_client_id = "google-client-id"
    settings.google_oauth_client_secret = "google-client-secret-123456"  # noqa: S105
    settings.google_oauth_expires_at = (
        (datetime.now(tz=UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    )
    _FakeGenAIClient.created.clear()
    monkeypatch.setattr(
        "mascarade.router.providers.google.genai.Client",
        _FakeGenAIClient,
    )

    provider = GoogleProvider()

    assert provider.is_configured is True
    client = provider._ensure_client()
    assert "credentials" in client.kwargs
    assert "api_key" not in client.kwargs
    assert client.kwargs.get("vertexai") is None


@pytest.mark.asyncio
async def test_google_provider_refreshes_oauth_token(monkeypatch):
    settings.google_auth_mode = "oauth_oidc"
    settings.google_oauth_access_token = ""  # noqa: S105
    settings.google_oauth_refresh_token = "1//refresh-token-123456789"  # noqa: S105
    settings.google_oauth_client_id = "google-client-id"
    settings.google_oauth_client_secret = "google-client-secret-123456"  # noqa: S105
    settings.google_oauth_token_endpoint = "https://oauth2.googleapis.com/token"  # noqa: S105
    _FakeGenAIClient.created.clear()
    monkeypatch.setattr(
        "mascarade.router.providers.google.genai.Client",
        _FakeGenAIClient,
    )

    def fake_refresh(self, _request):
        self.token = "ya29.refreshed_access_987654321"  # noqa: S105
        self.expiry = datetime.now(tz=UTC) + timedelta(hours=1)

    monkeypatch.setattr(
        "mascarade.router.providers.google.Credentials.refresh",
        fake_refresh,
    )

    provider = GoogleProvider()

    client = provider._ensure_client()
    credentials = client.kwargs["credentials"]
    assert credentials.token == "ya29.refreshed_access_987654321"  # noqa: S105
    assert settings.google_oauth_access_token == "ya29.refreshed_access_987654321"  # noqa: S105
    assert settings.google_oauth_expires_at


def test_google_provider_adc_mode_requires_project_and_credentials_path():
    settings.google_auth_mode = "adc"
    settings.google_cloud_project = "mascarade-test"
    settings.google_application_credentials = "/tmp/google-creds.json"  # noqa: S108

    provider = GoogleProvider()

    assert provider.is_configured is True
