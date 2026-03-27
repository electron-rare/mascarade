from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

# The deploy package lives outside core; make it importable.
_monorepo_root = str(Path(__file__).resolve().parents[2])
if _monorepo_root not in sys.path:
    sys.path.insert(0, _monorepo_root)

try:
    from deploy.ops_agent.app import (  # noqa: E402
        provider_clear_updates,
    )
except ImportError:
    provider_clear_updates = None

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
    assert entry["classification"] == "provider-credential"
    assert entry["criticality"] == "feature-required"
    assert entry["required_when"] == "Requis seulement si HuggingFace est active comme provider."
    assert entry["used_by"] == ["core", "playground", "orchestrate", "ops-agent"]
    assert entry["configured"] is True
    assert api_key_field["active"] is False
    assert refresh_field["active"] is True
    assert refresh_field["configured"] is True
    assert refresh_field["classification"] == "provider-credential"


def test_get_providers_status_ollama_toggle_disables_provider():
    settings.ollama_base_url = "http://ollama:11434"
    settings.ollama_enabled = False

    status = get_providers_status(_FakeRouter())
    entry = next(provider for provider in status if provider["name"] == "ollama")

    assert entry["enabled"] is False
    assert entry["configured"] is False
    assert entry["toggle_env"] == "OLLAMA_ENABLED"
    assert entry["classification"] == "provider-credential"
    assert entry["criticality"] == "feature-required"
    assert entry["required_when"] == "Requis seulement si le provider local Ollama est active."
    assert entry["used_by"] == ["core", "playground", "orchestrate"]
    assert entry["fields"][0]["classification"] == "operator-context"
    assert entry["fields"][0]["criticality"] == "local-operator-context"


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


@pytest.mark.skipif(provider_clear_updates is None, reason="deploy module not importable")
def test_provider_clear_updates_resets_toggle_and_fields():
    updates = provider_clear_updates(PROVIDER_REGISTRY["ollama"])

    assert updates == {
        "OLLAMA_BASE_URL": "",
        "OLLAMA_ENABLED": "false",
    }


@pytest.mark.skipif(provider_clear_updates is None, reason="deploy module not importable")
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


# ── Additional coverage ──


class TestResolveProviderMeta:
    """Tests for resolve_provider_meta."""

    def test_known_provider(self):
        from mascarade.provider_admin import resolve_provider_meta

        meta = resolve_provider_meta("claude")
        assert meta["label"] == "Anthropic / Claude"
        assert len(meta["fields"]) >= 1

    def test_unknown_provider_raises(self):
        from mascarade.provider_admin import resolve_provider_meta

        with pytest.raises(KeyError):
            resolve_provider_meta("nonexistent_provider")


class TestValidProviderEnvs:
    """Tests for valid_provider_envs."""

    def test_claude_envs(self):
        from mascarade.provider_admin import valid_provider_envs

        envs = valid_provider_envs(PROVIDER_REGISTRY["claude"])
        assert "ANTHROPIC_API_KEY" in envs

    def test_ollama_envs_include_toggle(self):
        from mascarade.provider_admin import valid_provider_envs

        envs = valid_provider_envs(PROVIDER_REGISTRY["ollama"])
        assert "OLLAMA_BASE_URL" in envs
        assert "OLLAMA_ENABLED" in envs

    def test_google_envs_include_auth_mode(self):
        from mascarade.provider_admin import valid_provider_envs

        envs = valid_provider_envs(PROVIDER_REGISTRY["google"])
        assert "GOOGLE_AUTH_MODE" in envs
        assert "GOOGLE_API_KEY" in envs


class TestMask:
    """Tests for _mask helper."""

    def test_short_secret(self):
        from mascarade.provider_admin import _mask

        assert _mask("short") == "***"

    def test_empty_secret(self):
        from mascarade.provider_admin import _mask

        assert _mask("") == ""

    def test_long_secret(self):
        from mascarade.provider_admin import _mask

        result = _mask("sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert result.endswith("cdef")
        assert "..." in result


class TestPersistEnv:
    """Tests for _persist_env."""

    def test_rejects_unknown_env_key(self):
        from mascarade.provider_admin import _persist_env

        with pytest.raises(ValueError, match="Refusing to persist unknown env key"):
            _persist_env({"MALICIOUS_VAR": "evil"})

    def test_writes_known_keys(self, tmp_path, monkeypatch):
        from mascarade.provider_admin import _persist_env

        env_file = tmp_path / ".env"
        env_file.write_text("ANTHROPIC_API_KEY=old-value\n")
        monkeypatch.chdir(tmp_path)

        _persist_env({"ANTHROPIC_API_KEY": "new-value"})

        content = env_file.read_text()
        assert "ANTHROPIC_API_KEY=new-value" in content
        assert "old-value" not in content

    def test_appends_new_keys(self, tmp_path, monkeypatch):
        from mascarade.provider_admin import _persist_env

        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=value\n")
        monkeypatch.chdir(tmp_path)

        _persist_env({"ANTHROPIC_API_KEY": "new-key"})

        content = env_file.read_text()
        assert "EXISTING=value" in content
        assert "ANTHROPIC_API_KEY=new-key" in content

    def test_creates_env_file_if_missing(self, tmp_path, monkeypatch):
        from mascarade.provider_admin import _persist_env

        monkeypatch.chdir(tmp_path)

        _persist_env({"ANTHROPIC_API_KEY": "fresh-key"})

        env_file = tmp_path / ".env"
        assert env_file.exists()
        assert "ANTHROPIC_API_KEY=fresh-key" in env_file.read_text()


class TestUpdateProviderKeysEdgeCases:
    """Additional edge cases for update_provider_keys."""

    def test_unknown_provider_returns_error(self):
        result = update_provider_keys("unknown_provider", {}, _FakeRouter())
        assert "error" in result
        assert "Unknown provider" in result["error"]

    def test_unknown_field_returns_error(self):
        result = update_provider_keys("claude", {"INVALID_ENV_VAR": "value"}, _FakeRouter())
        assert "error" in result
        assert "Unknown field" in result["error"]


class TestProviderRegistryStructure:
    """Tests for PROVIDER_REGISTRY consistency."""

    def test_all_providers_have_required_keys(self):
        required_keys = {"label", "classification", "criticality", "fields"}
        for name, meta in PROVIDER_REGISTRY.items():
            for key in required_keys:
                assert key in meta, f"Provider '{name}' missing key '{key}'"

    def test_all_fields_have_env_and_attr(self):
        for name, meta in PROVIDER_REGISTRY.items():
            for field in meta["fields"]:
                assert "env" in field, f"Provider '{name}' field missing 'env'"
                assert "attr" in field, f"Provider '{name}' field missing 'attr'"
