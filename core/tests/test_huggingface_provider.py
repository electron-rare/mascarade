from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

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


class _FakeAsyncOpenAI:
    created: list[dict] = []

    def __init__(self, *, api_key: str, base_url: str, timeout: float):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(
                    return_value=SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
                        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
                    )
                )
            )
        )
        self.__class__.created.append(
            {"api_key": api_key, "base_url": base_url, "timeout": timeout}
        )


class _FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeHttpxClient:
    calls: list[dict[str, object]] = []

    def __init__(self, *, timeout: float):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url: str, *, data: dict[str, str], headers: dict[str, str]):
        self.__class__.calls.append({"url": url, "data": data, "headers": headers})
        return _FakeResponse(
            {
                "access_token": "hf_oauth_access_123456789",
                "refresh_token": "hf_refresh_rotated_987654321",
                "expires_in": 3600,
            }
        )


@pytest.mark.asyncio
async def test_huggingface_provider_uses_api_key(monkeypatch):
    settings.huggingface_auth_mode = "api_key"
    settings.huggingface_api_key = "hf_api_key_123456789"  # noqa: S105
    settings.huggingface_base_url = "https://router.huggingface.co/v1"
    _FakeAsyncOpenAI.created.clear()
    monkeypatch.setattr(
        "mascarade.router.providers.huggingface.openai.AsyncOpenAI",
        _FakeAsyncOpenAI,
    )

    provider = HuggingFaceProvider()

    assert provider.is_configured is True
    client = await provider._ensure_client()
    assert client.api_key == "hf_api_key_123456789"  # noqa: S105
    assert _FakeAsyncOpenAI.created[-1]["api_key"] == "hf_api_key_123456789"  # noqa: S105


@pytest.mark.asyncio
async def test_huggingface_provider_refreshes_oauth_token(monkeypatch):
    settings.huggingface_auth_mode = "oauth_oidc"
    settings.huggingface_oauth_access_token = ""  # noqa: S105
    settings.huggingface_oauth_refresh_token = "hf_refresh_123456789"  # noqa: S105
    settings.huggingface_oauth_client_id = "hf-client-id"
    settings.huggingface_oauth_client_secret = "hf-client-secret-123456"  # noqa: S105
    settings.huggingface_oauth_token_endpoint = "https://huggingface.co/oauth/token"  # noqa: S105
    settings.huggingface_oauth_expires_at = ""

    _FakeAsyncOpenAI.created.clear()
    _FakeHttpxClient.calls.clear()
    monkeypatch.setattr(
        "mascarade.router.providers.huggingface.openai.AsyncOpenAI",
        _FakeAsyncOpenAI,
    )
    monkeypatch.setattr(
        "mascarade.router.providers.huggingface.httpx.AsyncClient",
        _FakeHttpxClient,
    )

    provider = HuggingFaceProvider()

    assert provider.is_configured is True
    client = await provider._ensure_client()

    assert client.api_key == "hf_oauth_access_123456789"  # noqa: S105
    assert settings.huggingface_oauth_access_token == "hf_oauth_access_123456789"  # noqa: S105
    assert settings.huggingface_oauth_refresh_token == "hf_refresh_rotated_987654321"  # noqa: S105
    assert settings.huggingface_oauth_expires_at
    assert _FakeHttpxClient.calls
    assert _FakeHttpxClient.calls[-1]["url"] == "https://huggingface.co/oauth/token"


def test_huggingface_provider_oauth_mode_is_configured_with_refresh_token_only():
    settings.huggingface_auth_mode = "oauth_oidc"
    settings.huggingface_oauth_access_token = ""  # noqa: S105
    settings.huggingface_oauth_refresh_token = "hf_refresh_123456789"  # noqa: S105
    settings.huggingface_oauth_client_id = "hf-client-id"
    settings.huggingface_oauth_client_secret = "hf-client-secret-123456"  # noqa: S105
    settings.huggingface_oauth_expires_at = _iso_utc_for_test(
        datetime.now(tz=UTC) - timedelta(seconds=5)
    )

    provider = HuggingFaceProvider()

    assert provider.is_configured is True


def _iso_utc_for_test(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
