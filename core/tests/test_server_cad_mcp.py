from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mascarade.auth import add_api_key, get_active_api_keys, remove_api_key
from mascarade.server import app


@pytest.fixture(autouse=True)
def _clean_api_keys():
    for key in get_active_api_keys():
        remove_api_key(key)
    yield
    for key in get_active_api_keys():
        remove_api_key(key)


@asynccontextmanager
async def _client():
    with patch("mascarade.auth.is_valid_api_key", return_value=True), \
         patch("mascarade.auth._resolve_role", return_value="admin"):
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                yield client


@pytest.mark.asyncio
async def test_freecad_create_document_route_uses_mcp_client():
    add_api_key("test-key-001")
    fake_mcp = AsyncMock()
    fake_mcp.freecad_create_document.return_value = {
        "ok": True,
        "document_path": ".cad-home/freecad/demo.FCStd",
        "document_name": "TraceDoc",
        "object_count": 1,
    }

    async with _client() as client:
        app.state.mcp = fake_mcp
        response = await client.post(
            "/mcp/freecad/documents",
            headers={"Authorization": "Bearer test-key-001"},
            json={
                "output_path": ".cad-home/freecad/demo.FCStd",
                "name": "TraceDoc",
                "run_id": "run-freecad-001",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-freecad-001"
    assert payload["document_name"] == "TraceDoc"
    fake_mcp.freecad_create_document.assert_awaited_once()
    call = fake_mcp.freecad_create_document.await_args
    assert call.args[0] == ".cad-home/freecad/demo.FCStd"
    assert call.kwargs["run_id"] == "run-freecad-001"
    assert call.kwargs["mode"] == "freecad"
    assert call.kwargs["agent_name"] == "freecad"


@pytest.mark.asyncio
async def test_openscad_render_route_generates_run_id_when_missing():
    add_api_key("test-key-001")
    fake_mcp = AsyncMock()
    fake_mcp.openscad_render_model.return_value = {
        "ok": True,
        "output_path": ".cad-home/openscad/demo.stl",
        "size_bytes": 128,
    }

    async with _client() as client:
        app.state.mcp = fake_mcp
        response = await client.post(
            "/mcp/openscad/render",
            headers={"Authorization": "Bearer test-key-001"},
            json={
                "source": "cube([10, 8, 6]);",
                "output_path": ".cad-home/openscad/demo.stl",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]
    fake_mcp.openscad_render_model.assert_awaited_once()
    call = fake_mcp.openscad_render_model.await_args
    assert call.args[:2] == ("cube([10, 8, 6]);", ".cad-home/openscad/demo.stl")
    assert call.kwargs["run_id"] == payload["run_id"]
    assert call.kwargs["mode"] == "openscad"
    assert call.kwargs["agent_name"] == "openscad"


@pytest.mark.asyncio
async def test_toolpath_generate_gcode_route():
    add_api_key("test-key-001")

    async with _client() as client:
        response = await client.post(
            "/v1/mcp/toolpath/generate",
            headers={"Authorization": "Bearer test-key-001"},
            json={
                "mesh": {
                    "vertices": [[0, 0, 0], [10, 0, 0], [10, 10, 0]],
                    "faces": [[0, 1, 2]],
                    "format": "stl",
                },
                "tool": {"id": "tool_1", "diameter": 6.0, "flute_count": 2},
                "strategy": "adaptive",
                "run_id": "run-toolpath-001",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["run_id"] == "run-toolpath-001"
    assert "gcode" in payload
    assert "toolpath" in payload
    assert payload["gcode"]["program"]
    assert payload["gcode"]["estimated_time_s"] > 0
    assert payload["toolpath"]["unit"] == "mm"
    assert payload["toolpath"]["tool_id"] == "tool_1"


@pytest.mark.asyncio
async def test_toolpath_generate_validates_strategy():
    add_api_key("test-key-001")

    async with _client() as client:
        response = await client.post(
            "/v1/mcp/toolpath/generate",
            headers={"Authorization": "Bearer test-key-001"},
            json={
                "mesh": {},
                "tool": {},
                "strategy": "invalid_strategy",
            },
        )

    assert response.status_code == 400
    assert "Invalid strategy" in response.json()["detail"]


@pytest.mark.asyncio
async def test_toolpath_optimize_route():
    add_api_key("test-key-001")

    async with _client() as client:
        response = await client.post(
            "/v1/mcp/toolpath/optimize",
            headers={"Authorization": "Bearer test-key-001"},
            json={
                "toolpath": {
                    "moves": [
                        {
                            "x": 0.0,
                            "y": 0.0,
                            "z": 10.0,
                            "feed_rate": 100.0,
                            "type": "rapid",
                        },
                        {
                            "x": 50.0,
                            "y": 50.0,
                            "z": 0.0,
                            "feed_rate": 50.0,
                            "type": "linear",
                        },
                    ],
                    "unit": "mm",
                    "tool_id": "tool_0",
                },
                "objective": "time",
                "run_id": "run-toolpath-opt-001",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["run_id"] == "run-toolpath-opt-001"
    assert "toolpath" in payload
    assert "gcode" in payload
    assert "improvement_pct" in payload
    assert payload["improvement_pct"] > 0


@pytest.mark.asyncio
async def test_toolpath_optimize_validates_objective():
    add_api_key("test-key-001")

    async with _client() as client:
        response = await client.post(
            "/v1/mcp/toolpath/optimize",
            headers={"Authorization": "Bearer test-key-001"},
            json={
                "toolpath": {"moves": [], "unit": "mm", "tool_id": "tool_0"},
                "objective": "invalid_objective",
            },
        )

    assert response.status_code == 400
    assert "Invalid objective" in response.json()["detail"]
