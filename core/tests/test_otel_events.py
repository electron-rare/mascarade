"""Tests for the OTLP HTTP event emitters in mascarade.observability.otel."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mascarade.observability.otel import (
    _parse_headers,
    _resource_attributes,
    _severity_number,
    emit_agent_prompt,
    emit_api_error,
    emit_api_request,
    emit_routing_decision,
    emit_tool_result,
    schedule_otlp_log,
)


class TestSeverityNumber:
    """Tests for _severity_number mapping."""

    def test_debug(self):
        assert _severity_number("debug") == 5

    def test_info(self):
        assert _severity_number("info") == 9

    def test_warning(self):
        assert _severity_number("warning") == 13

    def test_error(self):
        assert _severity_number("error") == 17

    def test_critical(self):
        assert _severity_number("critical") == 21

    def test_unknown_defaults_to_info(self):
        assert _severity_number("trace") == 9
        assert _severity_number("") == 9

    def test_case_insensitive(self):
        assert _severity_number("DEBUG") == 5
        assert _severity_number("Error") == 17


class TestParseHeaders:
    """Tests for _parse_headers."""

    def test_empty_string(self):
        assert _parse_headers("") == {}

    def test_single_header(self):
        result = _parse_headers("Authorization=Bearer token123")
        assert result == {"Authorization": "Bearer token123"}

    def test_multiple_headers(self):
        result = _parse_headers("Key1=Value1,Key2=Value2")
        assert result == {"Key1": "Value1", "Key2": "Value2"}

    def test_strips_whitespace(self):
        result = _parse_headers(" Key1 = Value1 , Key2 = Value2 ")
        assert result == {"Key1": "Value1", "Key2": "Value2"}

    def test_ignores_entries_without_equals(self):
        result = _parse_headers("Key1=Value1,garbage,Key2=Value2")
        assert "Key1" in result
        assert "Key2" in result
        assert len(result) == 2


class TestResourceAttributes:
    """Tests for _resource_attributes."""

    def test_includes_service_name(self):
        attrs = _resource_attributes()
        names = {a["key"] for a in attrs}
        assert "service.name" in names
        assert "service.version" in names

    def test_extra_attributes_from_config(self):
        with patch("mascarade.observability.otel.settings") as mock_settings:
            mock_settings.otel_service_name = "test-svc"
            mock_settings.otel_resource_attributes = "team.id=core,env=test"
            attrs = _resource_attributes()

        keys = {a["key"] for a in attrs}
        assert "team.id" in keys
        assert "env" in keys

    def test_no_extra_attributes(self):
        with patch("mascarade.observability.otel.settings") as mock_settings:
            mock_settings.otel_service_name = "mascarade-core"
            mock_settings.otel_resource_attributes = ""
            attrs = _resource_attributes()

        assert len(attrs) == 2  # service.name + service.version


class TestPostOtlpLog:
    """Tests for _post_otlp_log via schedule_otlp_log."""

    @pytest.mark.asyncio
    async def test_posts_to_collector_endpoint(self):
        with patch("mascarade.observability.otel.settings") as mock_settings:
            mock_settings.otel_enabled = True
            mock_settings.otel_collector_http_endpoint = "http://collector:4318"
            mock_settings.otel_exporter_headers = ""
            mock_settings.otel_service_name = "test"
            mock_settings.otel_resource_attributes = ""

            with patch("mascarade.observability.otel.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = AsyncMock(status_code=200)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_client.return_value = mock_instance

                from mascarade.observability.otel import _post_otlp_log

                await _post_otlp_log(
                    body="test message",
                    severity="info",
                    attributes={"key": "value"},
                )

                mock_instance.post.assert_called_once()
                call_url = mock_instance.post.call_args[0][0]
                assert call_url == "http://collector:4318/v1/logs"

    @pytest.mark.asyncio
    async def test_skips_when_no_endpoint(self):
        with patch("mascarade.observability.otel.settings") as mock_settings:
            mock_settings.otel_collector_http_endpoint = ""

            with patch("mascarade.observability.otel.httpx.AsyncClient") as mock_client:
                from mascarade.observability.otel import _post_otlp_log

                await _post_otlp_log(
                    body="test",
                    severity="info",
                    attributes={},
                )

                mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        with patch("mascarade.observability.otel.settings") as mock_settings:
            mock_settings.otel_enabled = True
            mock_settings.otel_collector_http_endpoint = "http://collector:4318"
            mock_settings.otel_exporter_headers = ""
            mock_settings.otel_service_name = "test"
            mock_settings.otel_resource_attributes = ""

            with patch("mascarade.observability.otel.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.side_effect = Exception("network error")
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_client.return_value = mock_instance

                from mascarade.observability.otel import _post_otlp_log

                # Should not raise
                await _post_otlp_log(
                    body="test",
                    severity="error",
                    attributes={"k": "v"},
                )

    @pytest.mark.asyncio
    async def test_custom_service_name_overrides_default(self):
        with patch("mascarade.observability.otel.settings") as mock_settings:
            mock_settings.otel_enabled = True
            mock_settings.otel_collector_http_endpoint = "http://collector:4318"
            mock_settings.otel_exporter_headers = ""
            mock_settings.otel_service_name = "default-svc"
            mock_settings.otel_resource_attributes = ""

            with patch("mascarade.observability.otel.httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post.return_value = AsyncMock(status_code=200)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                mock_client.return_value = mock_instance

                from mascarade.observability.otel import _post_otlp_log

                await _post_otlp_log(
                    service_name="custom-svc",
                    body="test",
                    severity="info",
                    attributes={},
                )

                payload = mock_instance.post.call_args.kwargs.get(
                    "json", mock_instance.post.call_args[1].get("json", {})
                )
                resource = payload["resourceLogs"][0]["resource"]
                svc_attr = next(
                    a for a in resource["attributes"] if a["key"] == "service.name"
                )
                assert svc_attr["value"]["stringValue"] == "custom-svc"


class TestScheduleOtlpLog:
    """Tests for schedule_otlp_log (fire-and-forget scheduler)."""

    def test_noop_when_otel_disabled(self):
        with patch("mascarade.observability.otel.settings") as mock_settings:
            mock_settings.otel_enabled = False

            with patch("mascarade.observability.otel._post_otlp_log") as mock_post:
                schedule_otlp_log(body="test", severity="info", attributes={})

                mock_post.assert_not_called()

    def test_noop_when_no_event_loop(self):
        with patch("mascarade.observability.otel.settings") as mock_settings:
            mock_settings.otel_enabled = True

            with (
                patch("mascarade.observability.otel.asyncio.get_running_loop", side_effect=RuntimeError),
                patch("mascarade.observability.otel._post_otlp_log"),
            ):
                # Should not raise
                schedule_otlp_log(body="test", severity="info", attributes={})


class TestEmitAgentPrompt:
    """Tests for emit_agent_prompt."""

    def test_calls_schedule_with_correct_attributes(self):
        with patch("mascarade.observability.otel.schedule_otlp_log") as mock_schedule:
            emit_agent_prompt(
                agent_name="test-agent",
                prompt_length=100,
                session_id="sess-1",
            )

            mock_schedule.assert_called_once()
            call_kwargs = mock_schedule.call_args.kwargs
            assert call_kwargs["severity"] == "info"
            assert "test-agent" in call_kwargs["body"]
            assert call_kwargs["attributes"]["agent.name"] == "test-agent"
            assert call_kwargs["attributes"]["prompt_length"] == "100"
            assert call_kwargs["attributes"]["session.id"] == "sess-1"

    def test_generates_prompt_id_when_not_provided(self):
        with patch("mascarade.observability.otel.schedule_otlp_log") as mock_schedule:
            emit_agent_prompt(agent_name="a", prompt_length=10)

            attrs = mock_schedule.call_args.kwargs["attributes"]
            assert attrs["prompt.id"]  # non-empty UUID


class TestEmitToolResult:
    """Tests for emit_tool_result."""

    def test_success_event(self):
        with patch("mascarade.observability.otel.schedule_otlp_log") as mock_schedule:
            emit_tool_result(
                prompt_id="p1",
                tool_name="bash",
                success=True,
                duration_ms=42.5,
            )

            call_kwargs = mock_schedule.call_args.kwargs
            assert call_kwargs["severity"] == "info"
            assert call_kwargs["attributes"]["success"] == "true"
            assert call_kwargs["attributes"]["duration_ms"] == "42.5"

    def test_error_event(self):
        with patch("mascarade.observability.otel.schedule_otlp_log") as mock_schedule:
            emit_tool_result(
                prompt_id="p1",
                tool_name="bash",
                success=False,
                duration_ms=10.0,
            )

            assert mock_schedule.call_args.kwargs["severity"] == "error"
            assert mock_schedule.call_args.kwargs["attributes"]["success"] == "false"


class TestEmitApiRequest:
    """Tests for emit_api_request."""

    def test_emits_with_token_counts(self):
        with patch("mascarade.observability.otel.schedule_otlp_log") as mock_schedule:
            emit_api_request(
                prompt_id="p1",
                provider="claude",
                model="claude-3-5-sonnet",
                input_tokens=100,
                output_tokens=50,
                duration_ms=1500.0,
                cost_usd=0.003,
            )

            attrs = mock_schedule.call_args.kwargs["attributes"]
            assert attrs["provider"] == "claude"
            assert attrs["model"] == "claude-3-5-sonnet"
            assert attrs["input_tokens"] == "100"
            assert attrs["output_tokens"] == "50"
            assert attrs["cost_usd"] == "0.003000"


class TestEmitApiError:
    """Tests for emit_api_error."""

    def test_emits_error_severity(self):
        with patch("mascarade.observability.otel.schedule_otlp_log") as mock_schedule:
            emit_api_error(
                prompt_id="p1",
                provider="openai",
                model="gpt-4o",
                error="rate_limited",
                status_code=429,
                duration_ms=200.0,
            )

            call_kwargs = mock_schedule.call_args.kwargs
            assert call_kwargs["severity"] == "error"
            assert call_kwargs["attributes"]["error"] == "rate_limited"
            assert call_kwargs["attributes"]["status_code"] == "429"


class TestEmitRoutingDecision:
    """Tests for emit_routing_decision."""

    def test_emits_routing_attributes(self):
        with patch("mascarade.observability.otel.schedule_otlp_log") as mock_schedule:
            emit_routing_decision(
                prompt_id="p1",
                strategy="cheapest",
                selected_provider="mistral",
                selected_model="mistral-large",
                candidates=5,
                duration_ms=3.2,
            )

            attrs = mock_schedule.call_args.kwargs["attributes"]
            assert attrs["strategy"] == "cheapest"
            assert attrs["selected_provider"] == "mistral"
            assert attrs["candidates"] == "5"
