"""Tests for QuilterProvider — Plan 26 EDA Phase 2."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mascarade.router.providers.quilter import (
    ACTIONS,
    IMPEDANCE_PRESETS,
    QuilterProvider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msg(payload: dict | str) -> list[dict]:
    content = json.dumps(payload) if isinstance(payload, dict) else payload
    return [{"role": "user", "content": content}]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def provider() -> QuilterProvider:
    return QuilterProvider(api_url="http://quilter.local:9090")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class TestConfiguration:
    def test_is_configured_with_url(self, provider):
        assert provider.is_configured is True

    def test_is_not_configured_without_url(self):
        p = QuilterProvider(api_url="")
        assert p.is_configured is False

    def test_default_attributes(self, provider):
        assert provider.name == "quilter"
        assert provider.default_model == "quilter-v1"
        assert provider.available_models() == ["quilter-v1"]
        assert provider.timeout == 120.0

    def test_env_fallback(self, monkeypatch):
        monkeypatch.setenv("QUILTER_API_URL", "http://quilter-env:7777")
        p = QuilterProvider()
        assert p.api_url == "http://quilter-env:7777"


# ---------------------------------------------------------------------------
# Invalid input
# ---------------------------------------------------------------------------

class TestInvalidInput:
    @pytest.mark.asyncio
    async def test_non_json_input(self, provider):
        resp = await provider.send(_msg("garbage"))
        body = json.loads(resp.content)
        assert "error" in body
        assert body["supported_actions"] == ACTIONS

    @pytest.mark.asyncio
    async def test_unknown_action(self, provider):
        resp = await provider.send(_msg({"action": "fly_to_mars"}))
        body = json.loads(resp.content)
        assert "Unknown action" in body["error"]


# ---------------------------------------------------------------------------
# Action: submit_job
# ---------------------------------------------------------------------------

class TestSubmitJob:
    @pytest.mark.asyncio
    async def test_submit_success(self, provider):
        api_resp = {"job_id": "qj-1", "status": "queued"}
        with patch.object(provider, "_post", new_callable=AsyncMock, return_value=api_resp):
            resp = await provider.send(_msg({
                "action": "submit_job",
                "file_path": "/tmp/board.kicad_pcb",
            }))
        body = json.loads(resp.content)
        assert body["job_id"] == "qj-1"

    @pytest.mark.asyncio
    async def test_submit_with_impedance_preset(self, provider):
        mock_post = AsyncMock(return_value={"job_id": "qj-2"})
        with patch.object(provider, "_post", mock_post):
            await provider.send(_msg({
                "action": "submit_job",
                "file_path": "/tmp/board.kicad_pcb",
                "impedance_preset": "50ohm_single",
            }))
        payload = mock_post.call_args[0][1]
        assert payload["impedance"]["target_ohm"] == 50

    @pytest.mark.asyncio
    async def test_submit_with_diff_impedance(self, provider):
        mock_post = AsyncMock(return_value={"job_id": "qj-3"})
        with patch.object(provider, "_post", mock_post):
            await provider.send(_msg({
                "action": "submit_job",
                "file_path": "/tmp/b.kicad_pcb",
                "impedance_preset": "100ohm_diff",
            }))
        payload = mock_post.call_args[0][1]
        assert payload["impedance"]["type"] == "differential"
        assert payload["impedance"]["trace_spacing_mm"] == 0.127

    @pytest.mark.asyncio
    async def test_submit_unknown_impedance_preset(self, provider):
        resp = await provider.send(_msg({
            "action": "submit_job",
            "file_path": "/tmp/b.kicad_pcb",
            "impedance_preset": "fantasy",
        }))
        body = json.loads(resp.content)
        assert "error" in body
        assert "available" in body

    @pytest.mark.asyncio
    async def test_submit_missing_file_path(self, provider):
        resp = await provider.send(_msg({"action": "submit_job"}))
        body = json.loads(resp.content)
        assert body["error"] == "file_path required"

    @pytest.mark.asyncio
    async def test_submit_no_impedance_sends_null(self, provider):
        mock_post = AsyncMock(return_value={"job_id": "qj-x"})
        with patch.object(provider, "_post", mock_post):
            await provider.send(_msg({
                "action": "submit_job",
                "file_path": "/tmp/b.kicad_pcb",
            }))
        payload = mock_post.call_args[0][1]
        assert payload["impedance"] is None


# ---------------------------------------------------------------------------
# Action: check_status
# ---------------------------------------------------------------------------

class TestCheckStatus:
    @pytest.mark.asyncio
    async def test_check_status_success(self, provider):
        api_resp = {"job_id": "qj-1", "status": "routing", "progress": 42}
        with patch.object(provider, "_get", new_callable=AsyncMock, return_value=api_resp):
            resp = await provider.send(_msg({"action": "check_status", "job_id": "qj-1"}))
        body = json.loads(resp.content)
        assert body["progress"] == 42

    @pytest.mark.asyncio
    async def test_check_status_missing_job_id(self, provider):
        resp = await provider.send(_msg({"action": "check_status"}))
        body = json.loads(resp.content)
        assert body["error"] == "job_id required"


# ---------------------------------------------------------------------------
# Action: list_candidates
# ---------------------------------------------------------------------------

class TestListCandidates:
    @pytest.mark.asyncio
    async def test_list_candidates_success(self, provider):
        api_resp = {"candidates": [
            {"id": "c1", "score": 0.95, "vias": 12},
            {"id": "c2", "score": 0.88, "vias": 18},
        ]}
        with patch.object(provider, "_get", new_callable=AsyncMock, return_value=api_resp):
            resp = await provider.send(_msg({"action": "list_candidates", "job_id": "qj-1"}))
        body = json.loads(resp.content)
        assert len(body["candidates"]) == 2

    @pytest.mark.asyncio
    async def test_list_candidates_missing_job_id(self, provider):
        resp = await provider.send(_msg({"action": "list_candidates"}))
        body = json.loads(resp.content)
        assert body["error"] == "job_id required"


# ---------------------------------------------------------------------------
# Action: download_result
# ---------------------------------------------------------------------------

class TestDownloadResult:
    @pytest.mark.asyncio
    async def test_download_success(self, provider):
        api_resp = {"file_url": "https://cdn.quilter.io/result.kicad_pcb"}
        mock_post = AsyncMock(return_value=api_resp)
        with patch.object(provider, "_post", mock_post):
            resp = await provider.send(_msg({
                "action": "download_result",
                "job_id": "qj-1",
                "candidate_id": "c1",
                "format": "kicad_pcb",
            }))
        body = json.loads(resp.content)
        assert "file_url" in body
        payload = mock_post.call_args[0][1]
        assert payload["candidate_id"] == "c1"

    @pytest.mark.asyncio
    async def test_download_default_candidate(self, provider):
        mock_post = AsyncMock(return_value={"ok": True})
        with patch.object(provider, "_post", mock_post):
            await provider.send(_msg({
                "action": "download_result",
                "job_id": "qj-1",
            }))
        payload = mock_post.call_args[0][1]
        assert payload["candidate_id"] == "best"

    @pytest.mark.asyncio
    async def test_download_missing_job_id(self, provider):
        resp = await provider.send(_msg({"action": "download_result"}))
        body = json.loads(resp.content)
        assert body["error"] == "job_id required"


# ---------------------------------------------------------------------------
# Action: set_constraints
# ---------------------------------------------------------------------------

class TestSetConstraints:
    @pytest.mark.asyncio
    async def test_set_constraints_success(self, provider):
        constraints = {"max_vias": 50, "max_layers": 2}
        api_resp = {"ok": True, "constraints": constraints}
        mock_post = AsyncMock(return_value=api_resp)
        with patch.object(provider, "_post", mock_post):
            resp = await provider.send(_msg({
                "action": "set_constraints",
                "job_id": "qj-1",
                "constraints": constraints,
            }))
        body = json.loads(resp.content)
        assert body["ok"] is True
        # The constraints dict is sent directly
        assert mock_post.call_args[0][1] == constraints

    @pytest.mark.asyncio
    async def test_set_constraints_missing_job_id(self, provider):
        resp = await provider.send(_msg({
            "action": "set_constraints",
            "constraints": {"max_vias": 10},
        }))
        body = json.loads(resp.content)
        assert body["error"] == "job_id required"

    @pytest.mark.asyncio
    async def test_set_constraints_empty(self, provider):
        resp = await provider.send(_msg({
            "action": "set_constraints",
            "job_id": "qj-1",
        }))
        body = json.loads(resp.content)
        assert body["error"] == "constraints dict required"


# ---------------------------------------------------------------------------
# Action: get_stackup
# ---------------------------------------------------------------------------

class TestGetStackup:
    @pytest.mark.asyncio
    async def test_get_all_presets(self, provider):
        resp = await provider.send(_msg({"action": "get_stackup"}))
        body = json.loads(resp.content)
        assert "presets" in body
        assert "jlc2313" in body["presets"]
        assert "50ohm_single" in body["presets"]

    @pytest.mark.asyncio
    async def test_get_specific_preset(self, provider):
        resp = await provider.send(_msg({"action": "get_stackup", "preset": "jlc2313"}))
        body = json.loads(resp.content)
        assert body["preset"] == "jlc2313"
        stackup = body["stackup"]
        assert stackup["total_thickness_mm"] == 1.6
        assert len(stackup["layers"]) == 7

    @pytest.mark.asyncio
    async def test_get_unknown_preset(self, provider):
        resp = await provider.send(_msg({"action": "get_stackup", "preset": "xyz"}))
        body = json.loads(resp.content)
        assert "error" in body
        assert "available" in body


# ---------------------------------------------------------------------------
# Impedance presets data
# ---------------------------------------------------------------------------

class TestImpedancePresets:
    def test_50ohm_single(self):
        p = IMPEDANCE_PRESETS["50ohm_single"]
        assert p["type"] == "single_ended"
        assert p["target_ohm"] == 50
        assert p["trace_width_mm"] == 0.2

    def test_100ohm_diff(self):
        p = IMPEDANCE_PRESETS["100ohm_diff"]
        assert p["type"] == "differential"
        assert p["target_ohm"] == 100
        assert p["trace_spacing_mm"] == 0.127

    def test_jlc2313_stackup(self):
        p = IMPEDANCE_PRESETS["jlc2313"]
        assert p["type"] == "stackup"
        assert p["total_thickness_mm"] == 1.6
        copper_layers = [l for l in p["layers"] if l["type"] == "copper"]
        assert len(copper_layers) == 4
        assert p["impedance_profiles"]["single_50"]["trace_width_mm"] == 0.224


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_api_http_error(self, provider):
        exc_resp = httpx.Response(
            status_code=500,
            request=httpx.Request("POST", "http://test"),
        )
        exc = httpx.HTTPStatusError("Internal Server Error", request=exc_resp.request, response=exc_resp)
        with patch.object(provider, "_post", new_callable=AsyncMock, side_effect=exc):
            resp = await provider.send(_msg({
                "action": "submit_job",
                "file_path": "/tmp/b.kicad_pcb",
            }))
        body = json.loads(resp.content)
        assert body["status_code"] == 500

    @pytest.mark.asyncio
    async def test_api_connection_error(self, provider):
        with patch.object(provider, "_get", new_callable=AsyncMock, side_effect=RuntimeError("connection refused")):
            resp = await provider.send(_msg({"action": "check_status", "job_id": "qj-1"}))
        body = json.loads(resp.content)
        assert "connection refused" in body["error"]

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
    async def test_stream_yields_single_chunk(self, provider):
        api_resp = {"job_id": "qj-stream"}
        with patch.object(provider, "_post", new_callable=AsyncMock, return_value=api_resp):
            chunks = [c async for c in provider.stream(_msg({
                "action": "submit_job",
                "file_path": "/tmp/b.kicad_pcb",
            }))]
        assert len(chunks) == 1
        assert json.loads(chunks[0])["job_id"] == "qj-stream"
