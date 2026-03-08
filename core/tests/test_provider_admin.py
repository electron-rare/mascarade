from __future__ import annotations

import sys
from types import ModuleType

import pytest
from deploy.ops_agent.app import provider_clear_updates

from mascarade.config import settings
from mascarade.provider_admin import (
    PROVIDER_REGISTRY,
    get_providers_status,
    update_provider_keys,
)

PROVIDER_SETTING_NAMES = [
    "huggingface_auth_mode",
    "huggingface_api_key",
    "huggingface_oauth_access_token",
    "huggingface_oauth_refresh_token",
    "huggingface_oauth_client_id",
    "huggingface_oauth_client_secret",
    "huggingface_oauth_token_endpoint",
    "huggingface_oauth_expires_at",
    "ollama_base_url",
    "ollama_enabled",
]


@pytest.fixture(autouse=True)
def restore_provider_settings():
    snapshot = {name: getattr(settings, name) for name in PROVIDER_SETTING_NAMES}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


class _FakeProvider:
    name = "ollama"
    default_model = "fake-model"

    def __init__(self):
        self.is_configured = True

    def available_models(self) -> list[str]:
        return ["fake-model"]


class _FakeRouter:
    def __init__(self):
        self.available_providers: list[str] = []
        self._providers: dict[str, object] = {}

    def register(self, provider) -> None:
        self._providers[provider.name] = provider
        if provider.name not in self.available_providers:
            self.available_providers.append(provider.name)


def test_get_providers_status_huggingface_oauth_uses_refresh_token():
    settings.huggingface_auth_mode = "oauth_oidc"
    settings.huggingface_api_key = ""  # noqa: S105
    settings.huggingface_oauth_access_token = ""  # noqa: S105
    settings.huggingface_oauth_refresh_token = "hf_refresh_123456789"  # noqa: S105
    settings.huggingface_oauth_client_id = "hf-client-id"
    settings.huggingface_oauth_client_secret = "hf-client-secret-123456"  # noqa: S105
    settings.huggingface_oauth_token_endpoint = "https://huggingface.co/oauth/token"  # noqa: S105

    status = get_providers_status(_FakeRouter())
    entry = next(provider for provider in status if provider["name"] == "huggingface")
    api_key_field = next(
        field for field in entry["fields"] if field["env"] == "HUGGINGFACE_API_KEY"
    )
    refresh_field = next(
        field for field in entry["fields"] if field["env"] == "HUGGINGFACE_OAUTH_REFRESH_TOKEN"
    )

    assert entry["auth_mode"] == "oauth_oidc"
    assert entry["configured"] is True
    assert api_key_field["active"] is False
    assert refresh_field["active"] is True
    assert refresh_field["configured"] is True


def test_get_providers_status_ollama_toggle_disables_provider():
    settings.ollama_base_url = "http://ollama:11434"
    settings.ollama_enabled = False

    status = get_providers_status(_FakeRouter())
    entry = next(provider for provider in status if provider["name"] == "ollama")

    assert entry["enabled"] is False
    assert entry["configured"] is False
    assert entry["toggle_env"] == "OLLAMA_ENABLED"


def test_update_provider_keys_reinitializes_provider_from_registry(monkeypatch):
    fake_module = ModuleType("test_provider_admin_fake")
    fake_module.FakeProvider = _FakeProvider
    router = _FakeRouter()

    monkeypatch.setitem(sys.modules, "test_provider_admin_fake", fake_module)
    monkeypatch.setitem(PROVIDER_REGISTRY["ollama"], "module", "test_provider_admin_fake")
    monkeypatch.setitem(PROVIDER_REGISTRY["ollama"], "class", "FakeProvider")
    monkeypatch.setattr("mascarade.provider_admin._persist_env", lambda updates: None)

    result = update_provider_keys(
        "ollama",
        {"OLLAMA_ENABLED": "yes", "OLLAMA_BASE_URL": "http://example.invalid:11434"},
        router,
    )

    assert result == {"status": "ok", "active": True}
    assert settings.ollama_enabled is True
    assert settings.ollama_base_url == "http://example.invalid:11434"
    assert "ollama" in router.available_providers
    assert isinstance(router._providers["ollama"], _FakeProvider)


def test_update_provider_keys_rejects_invalid_auth_mode():
    settings.huggingface_auth_mode = "api_key"

    result = update_provider_keys(
        "huggingface",
        {"HUGGINGFACE_AUTH_MODE": "totally-invalid"},
        _FakeRouter(),
    )

    assert result == {"error": "Invalid auth mode: totally-invalid"}
    assert settings.huggingface_auth_mode == "api_key"


def test_update_provider_keys_runtime_only_skips_env_persistence(monkeypatch):
    fake_module = ModuleType("test_provider_admin_fake_runtime")
    fake_module.FakeProvider = _FakeProvider
    router = _FakeRouter()

    monkeypatch.setitem(sys.modules, "test_provider_admin_fake_runtime", fake_module)
    monkeypatch.setitem(PROVIDER_REGISTRY["ollama"], "module", "test_provider_admin_fake_runtime")
    monkeypatch.setitem(PROVIDER_REGISTRY["ollama"], "class", "FakeProvider")

    def fail_persist(_updates):
        raise AssertionError("_persist_env should not be called in runtime-only mode")

    monkeypatch.setattr("mascarade.provider_admin._persist_env", fail_persist)

    result = update_provider_keys(
        "ollama",
        {"OLLAMA_ENABLED": "false"},
        router,
        persist_env=False,
    )

    assert result == {
        "status": "ok",
        "active": True,
        "message": "Core runtime updated only; use the API facade for durable .env persistence",
    }
    assert settings.ollama_enabled is False


def test_provider_clear_updates_resets_toggle_and_fields():
    updates = provider_clear_updates(PROVIDER_REGISTRY["ollama"])

    assert updates == {
        "OLLAMA_BASE_URL": "",
        "OLLAMA_ENABLED": "false",
    }


def test_provider_clear_updates_can_reset_selected_auth_fields_only():
    updates = provider_clear_updates(
        PROVIDER_REGISTRY["huggingface"],
        [
            "HUGGINGFACE_AUTH_MODE",
            "HUGGINGFACE_OAUTH_CLIENT_ID",
            "HUGGINGFACE_OAUTH_CLIENT_SECRET",
        ],
    )

    assert updates == {
        "HUGGINGFACE_AUTH_MODE": "api_key",
        "HUGGINGFACE_OAUTH_CLIENT_ID": "",
        "HUGGINGFACE_OAUTH_CLIENT_SECRET": "",
    }
