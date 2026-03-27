"""Tests for mascarade.observability.openllmetry — OpenLLMetry integration."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_module():
    """Force-reload the openllmetry module so import-time side effects are fresh."""
    mod_name = "mascarade.observability.openllmetry"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    return importlib.import_module(mod_name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInitWhenTraceloopMissing:
    """init_openllmetry must degrade gracefully when traceloop-sdk is absent."""

    def test_returns_false_when_not_installed(self):
        with patch.dict(sys.modules, {"traceloop": None, "traceloop.sdk": None}):
            mod = _reload_module()
            assert mod.init_openllmetry() is False

    def test_logs_warning_when_not_installed(self, caplog):
        with patch.dict(sys.modules, {"traceloop": None, "traceloop.sdk": None}):
            mod = _reload_module()
            with caplog.at_level("WARNING"):
                mod.init_openllmetry()
            assert "traceloop-sdk not installed" in caplog.text


class TestInitWhenTraceloopAvailable:
    """init_openllmetry must call Traceloop.init() when sdk is importable."""

    def test_calls_traceloop_init(self):
        mock_traceloop = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Traceloop = mock_traceloop

        with patch.dict(
            sys.modules,
            {"traceloop": MagicMock(), "traceloop.sdk": mock_sdk},
        ):
            mod = _reload_module()
            result = mod.init_openllmetry()

        assert result is True
        mock_traceloop.init.assert_called_once()

    def test_passes_app_name_from_settings(self):
        mock_traceloop = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Traceloop = mock_traceloop

        with (
            patch.dict(
                sys.modules,
                {"traceloop": MagicMock(), "traceloop.sdk": mock_sdk},
            ),
            patch("mascarade.observability.openllmetry.settings") as mock_settings,
        ):
            mock_settings.otel_service_name = "test-service"
            mock_settings.otel_collector_http_endpoint = "http://localhost:4318"
            mock_settings.otel_resource_attributes = ""
            mock_settings.otel_exporter_headers = ""
            mod = _reload_module()
            mod.init_openllmetry()

        call_kwargs = mock_traceloop.init.call_args
        assert call_kwargs[1]["app_name"] == "test-service"

    def test_returns_false_on_init_exception(self):
        mock_traceloop = MagicMock()
        mock_traceloop.init.side_effect = RuntimeError("boom")
        mock_sdk = MagicMock()
        mock_sdk.Traceloop = mock_traceloop

        with patch.dict(
            sys.modules,
            {"traceloop": MagicMock(), "traceloop.sdk": mock_sdk},
        ):
            mod = _reload_module()
            assert mod.init_openllmetry() is False


class TestConfigPropagation:
    """Environment variables are forwarded from mascarade settings."""

    def test_sets_otlp_endpoint_env(self):
        mock_traceloop = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Traceloop = mock_traceloop

        with (
            patch.dict(
                sys.modules,
                {"traceloop": MagicMock(), "traceloop.sdk": mock_sdk},
            ),
            patch.dict("os.environ", {}, clear=False),
            patch("mascarade.observability.openllmetry.settings") as mock_settings,
        ):
            mock_settings.otel_collector_http_endpoint = "http://collector:4318"
            mock_settings.otel_service_name = "mascarade-core"
            mock_settings.otel_resource_attributes = "team.id=core"
            mock_settings.otel_exporter_headers = "Authorization=Bearer tok"
            mod = _reload_module()
            mod.init_openllmetry()

            import os

            assert os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") == "http://collector:4318"
            assert os.environ.get("OTEL_SERVICE_NAME") == "mascarade-core"
            assert os.environ.get("OTEL_RESOURCE_ATTRIBUTES") == "team.id=core"
            assert os.environ.get("OTEL_EXPORTER_OTLP_HEADERS") == "Authorization=Bearer tok"

    def test_does_not_overwrite_existing_env(self):
        mock_traceloop = MagicMock()
        mock_sdk = MagicMock()
        mock_sdk.Traceloop = mock_traceloop

        with (
            patch.dict(
                sys.modules,
                {"traceloop": MagicMock(), "traceloop.sdk": mock_sdk},
            ),
            patch.dict(
                "os.environ",
                {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://already-set:4318"},
                clear=False,
            ),
            patch("mascarade.observability.openllmetry.settings") as mock_settings,
        ):
            mock_settings.otel_collector_http_endpoint = "http://should-not-win:4318"
            mock_settings.otel_service_name = "mascarade-core"
            mock_settings.otel_resource_attributes = ""
            mock_settings.otel_exporter_headers = ""
            mod = _reload_module()
            mod.init_openllmetry()

            import os

            assert os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://already-set:4318"


class TestDisableFlag:
    """The feature is gated behind settings.openllmetry_enabled."""

    def test_config_default_is_false(self):
        from mascarade.config import Settings

        s = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.openllmetry_enabled is False

    def test_config_respects_env_true(self):
        with patch.dict("os.environ", {"OPENLLMETRY_ENABLED": "true"}, clear=False):
            from mascarade.config import Settings

            s = Settings(
                _env_file=None,  # type: ignore[call-arg]
            )
            assert s.openllmetry_enabled is True
