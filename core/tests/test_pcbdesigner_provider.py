"""Tests for PCBDesignerProvider — Plan 26 EDA Phase 2."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mascarade.router.providers.pcbdesigner import (
    ACTIONS,
    DESIGN_RULES,
    PCBDesignerProvider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _msg(payload: dict | str) -> list[dict]:
    """Build a minimal messages list for provider.send()."""
    content = json.dumps(payload) if isinstance(payload, dict) else payload
    return [{"role": "user", "content": content}]


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> httpx.Response:
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("POST", "http://test"),
    )
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def provider() -> PCBDesignerProvider:
    return PCBDesignerProvider(api_url="http://pcbdesigner.local:8080")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestConfiguration:
    def test_is_configured_with_url(self, provider: PCBDesignerProvider):
        assert provider.is_configured is True

    def test_is_not_configured_without_url(self):
        p = PCBDesignerProvider(api_url="")
        assert p.is_configured is False

    def test_default_attributes(self, provider: PCBDesignerProvider):
        assert provider.name == "pcbdesigner"
        assert provider.default_model == "pcbdesigner-v1"
        assert provider.available_models() == ["pcbdesigner-v1"]

    def test_env_fallback(self, monkeypatch):
        monkeypatch.setenv("PCBDESIGNER_API_URL", "http://from-env:9000")
        p = PCBDesignerProvider()
        assert p.api_url == "http://from-env:9000"


# ---------------------------------------------------------------------------
# Invalid input
# ---------------------------------------------------------------------------


class TestInvalidInput:
    @pytest.mark.asyncio
    async def test_non_json_input(self, provider):
        resp = await provider.send(_msg("not json"))
        body = json.loads(resp.content)
        assert "error" in body
        assert "supported_actions" in body

    @pytest.mark.asyncio
    async def test_unknown_action(self, provider):
        resp = await provider.send(_msg({"action": "nope"}))
        body = json.loads(resp.content)
        assert body["error"].startswith("Unknown action")
        assert body["supported_actions"] == ACTIONS


# ---------------------------------------------------------------------------
# Action: upload_design
# ---------------------------------------------------------------------------


class TestUploadDesign:
    @pytest.mark.asyncio
    async def test_upload_success(self, provider):
        api_resp = {"job_id": "job-123", "status": "queued"}
        with patch.object(provider, "_post", new_callable=AsyncMock, return_value=api_resp):
            resp = await provider.send(
                _msg(
                    {
                        "action": "upload_design",
                        "file_path": "/tmp/board.kicad_pcb",
                        "rules_preset": "jlcpcb_2layer",
                    }
                )
            )
        body = json.loads(resp.content)
        assert body["job_id"] == "job-123"
        assert resp.provider == "pcbdesigner"

    @pytest.mark.asyncio
    async def test_upload_missing_file_path(self, provider):
        resp = await provider.send(_msg({"action": "upload_design"}))
        body = json.loads(resp.content)
        assert body["error"] == "file_path required"

    @pytest.mark.asyncio
    async def test_upload_with_pcbway_preset(self, provider):
        api_resp = {"job_id": "job-456", "status": "queued"}
        mock_post = AsyncMock(return_value=api_resp)
        with patch.object(provider, "_post", mock_post):
            await provider.send(
                _msg(
                    {
                        "action": "upload_design",
                        "file_path": "/tmp/board.kicad_pcb",
                        "rules_preset": "pcbway",
                    }
                )
            )
        call_payload = mock_post.call_args[0][1]
        assert call_payload["rules"]["name"] == "PCBWay Standard"

    @pytest.mark.asyncio
    async def test_upload_unknown_preset_falls_back(self, provider):
        """Unknown preset falls back to jlcpcb_2layer."""
        api_resp = {"job_id": "job-789"}
        mock_post = AsyncMock(return_value=api_resp)
        with patch.object(provider, "_post", mock_post):
            await provider.send(
                _msg(
                    {
                        "action": "upload_design",
                        "file_path": "/tmp/x.kicad_pcb",
                        "rules_preset": "nonexistent",
                    }
                )
            )
        call_payload = mock_post.call_args[0][1]
        assert call_payload["rules"]["name"] == "JLCPCB 2-Layer"


# ---------------------------------------------------------------------------
# Action: check_status
# ---------------------------------------------------------------------------


class TestCheckStatus:
    @pytest.mark.asyncio
    async def test_check_status_success(self, provider):
        api_resp = {"job_id": "job-1", "status": "completed", "progress": 100}
        with patch.object(provider, "_get", new_callable=AsyncMock, return_value=api_resp):
            resp = await provider.send(_msg({"action": "check_status", "job_id": "job-1"}))
        body = json.loads(resp.content)
        assert body["status"] == "completed"

    @pytest.mark.asyncio
    async def test_check_status_missing_job_id(self, provider):
        resp = await provider.send(_msg({"action": "check_status"}))
        body = json.loads(resp.content)
        assert body["error"] == "job_id required"


# ---------------------------------------------------------------------------
# Action: export_gerber
# ---------------------------------------------------------------------------


class TestExportGerber:
    @pytest.mark.asyncio
    async def test_export_gerber_success(self, provider):
        api_resp = {"url": "https://cdn.example.com/gerber.zip"}
        with patch.object(provider, "_post", new_callable=AsyncMock, return_value=api_resp):
            resp = await provider.send(
                _msg(
                    {
                        "action": "export_gerber",
                        "job_id": "job-1",
                        "format": "gerber_x2",
                        "include_drill": True,
                    }
                )
            )
        body = json.loads(resp.content)
        assert "url" in body

    @pytest.mark.asyncio
    async def test_export_gerber_missing_job_id(self, provider):
        resp = await provider.send(_msg({"action": "export_gerber"}))
        body = json.loads(resp.content)
        assert body["error"] == "job_id required"


# ---------------------------------------------------------------------------
# Action: order_pcb
# ---------------------------------------------------------------------------


class TestOrderPCB:
    @pytest.mark.asyncio
    async def test_order_pcb_success(self, provider):
        api_resp = {"order_id": "ord-42", "manufacturer": "jlcpcb", "quantity": 10}
        mock_post = AsyncMock(return_value=api_resp)
        with patch.object(provider, "_post", mock_post):
            resp = await provider.send(
                _msg(
                    {
                        "action": "order_pcb",
                        "job_id": "job-1",
                        "manufacturer": "jlcpcb",
                        "quantity": 10,
                    }
                )
            )
        body = json.loads(resp.content)
        assert body["order_id"] == "ord-42"
        call_payload = mock_post.call_args[0][1]
        assert call_payload["quantity"] == 10

    @pytest.mark.asyncio
    async def test_order_pcb_missing_job_id(self, provider):
        resp = await provider.send(_msg({"action": "order_pcb"}))
        body = json.loads(resp.content)
        assert body["error"] == "job_id required"

    @pytest.mark.asyncio
    async def test_order_pcb_default_quantity(self, provider):
        mock_post = AsyncMock(return_value={"order_id": "ord-99"})
        with patch.object(provider, "_post", mock_post):
            await provider.send(_msg({"action": "order_pcb", "job_id": "job-1"}))
        call_payload = mock_post.call_args[0][1]
        assert call_payload["quantity"] == 5
        assert call_payload["manufacturer"] == "jlcpcb"


# ---------------------------------------------------------------------------
# Action: get_rules
# ---------------------------------------------------------------------------


class TestGetRules:
    @pytest.mark.asyncio
    async def test_get_all_presets(self, provider):
        resp = await provider.send(_msg({"action": "get_rules"}))
        body = json.loads(resp.content)
        assert "presets" in body
        assert set(body["presets"].keys()) == {"jlcpcb_2layer", "jlcpcb_4layer", "pcbway"}

    @pytest.mark.asyncio
    async def test_get_specific_preset(self, provider):
        resp = await provider.send(_msg({"action": "get_rules", "preset": "jlcpcb_4layer"}))
        body = json.loads(resp.content)
        assert body["preset"] == "jlcpcb_4layer"
        assert body["rules"]["layers"] == 4
        assert body["rules"]["impedance_control"] is True

    @pytest.mark.asyncio
    async def test_get_unknown_preset(self, provider):
        resp = await provider.send(_msg({"action": "get_rules", "preset": "fantasy"}))
        body = json.loads(resp.content)
        assert "error" in body
        assert "available" in body


# ---------------------------------------------------------------------------
# Design rule presets data
# ---------------------------------------------------------------------------


class TestDesignRulePresets:
    def test_jlcpcb_2layer_values(self):
        r = DESIGN_RULES["jlcpcb_2layer"]
        assert r["layers"] == 2
        assert r["min_trace_mm"] == 0.127
        assert r["surface_finish"] == "HASL"

    def test_jlcpcb_4layer_stackup(self):
        r = DESIGN_RULES["jlcpcb_4layer"]
        assert r["layers"] == 4
        assert len(r["stackup"]) == 4
        assert r["stackup"][0] == "F.Cu"

    def test_pcbway_values(self):
        r = DESIGN_RULES["pcbway"]
        assert r["min_trace_mm"] == 0.1
        assert r["min_via_drill_mm"] == 0.2


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_api_http_error(self, provider):
        """HTTPStatusError is caught and returned as error JSON."""
        exc_resp = httpx.Response(
            status_code=503,
            request=httpx.Request("POST", "http://test"),
        )
        exc = httpx.HTTPStatusError(
            "Service Unavailable", request=exc_resp.request, response=exc_resp
        )
        with patch.object(provider, "_post", new_callable=AsyncMock, side_effect=exc):
            resp = await provider.send(
                _msg(
                    {
                        "action": "upload_design",
                        "file_path": "/tmp/b.kicad_pcb",
                    }
                )
            )
        body = json.loads(resp.content)
        assert "error" in body
        assert body["status_code"] == 503

    @pytest.mark.asyncio
    async def test_api_generic_exception(self, provider):
        """Generic exceptions are caught and returned as error JSON."""
        with patch.object(
            provider, "_post", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ):
            resp = await provider.send(
                _msg(
                    {
                        "action": "upload_design",
                        "file_path": "/tmp/b.kicad_pcb",
                    }
                )
            )
        body = json.loads(resp.content)
        assert "error" in body
        assert "boom" in body["error"]

    @pytest.mark.asyncio
    async def test_empty_messages(self, provider):
        resp = await provider.send([])
        body = json.loads(resp.content)
        assert "error" in body


# ---------------------------------------------------------------------------
# Stream
# ---------------------------------------------------------------------------


class TestStream:
    @pytest.mark.asyncio
    async def test_stream_yields_content(self, provider):
        with patch.object(provider, "_post", new_callable=AsyncMock, return_value={"ok": True}):
            chunks = []
            async for chunk in provider.stream(
                _msg(
                    {
                        "action": "upload_design",
                        "file_path": "/tmp/b.kicad_pcb",
                    }
                )
            ):
                chunks.append(chunk)
        assert len(chunks) == 1
        body = json.loads(chunks[0])
        assert body["ok"] is True
