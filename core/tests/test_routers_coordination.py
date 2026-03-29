"""HTTP integration tests for mascarade.routers.coordination."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.auth import require_auth
from mascarade.routers.coordination import router as coordination_router


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.run = AsyncMock(return_value=_mock_run("coder"))


def _mock_run(*names: str) -> SimpleNamespace:
    results = []
    for name in names:
        response = SimpleNamespace(content=f"ok-{name}", provider="mock", model="m")
        results.append(SimpleNamespace(agent_name=name, response=response, error=None))
    return SimpleNamespace(results=results)


def _mk_agent(name: str, cluster: str | None, capabilities: list[str]) -> Agent:
    return Agent(
        name=name,
        description=f"Agent {name}",
        system_prompt=f"You are {name}.",
        cluster=cluster,
        capabilities=capabilities,
    )


def _make_registry() -> AgentRegistry:
    reg = AgentRegistry(storage_path=None)
    reg.register(_mk_agent("agent-zero", "general", []), builtin=True)
    reg.register(_mk_agent("coder", "code", ["code", "debug"]), builtin=True)
    reg.register(_mk_agent("kicad", "electronics", ["pcb", "drc"]), builtin=True)
    reg.register(_mk_agent("spice", "electronics", ["simulation"]), builtin=True)
    return reg


def _make_app(*, with_registry: bool = True, with_orchestrator: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(coordination_router)
    app.dependency_overrides[require_auth] = lambda: True
    if with_registry:
        app.state.registry = _make_registry()
    if with_orchestrator:
        app.state.orchestrator = _FakeOrchestrator()
    return app


@asynccontextmanager
async def _client(*, with_registry: bool = True, with_orchestrator: bool = True):
    app = _make_app(with_registry=with_registry, with_orchestrator=with_orchestrator)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


class TestCoordinationRun:
    @pytest.mark.asyncio
    async def test_run_success_sequential(self):
        async with _client() as c:
            resp = await c.post(
                "/v1/api/coordination/run",
                json={"task": "debug this code", "mode": "sequential"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["mode"] == "sequential"
        assert data["task_id"]
        assert data["agents_used"]

    @pytest.mark.asyncio
    async def test_run_success_parallel(self):
        async with _client() as c:
            resp = await c.post(
                "/v1/api/coordination/run",
                json={"task": "run kicad checks", "mode": "parallel", "domain": "kicad"},
            )

        assert resp.status_code == 200
        assert resp.json()["mode"] == "parallel"

    @pytest.mark.asyncio
    async def test_run_success_pipeline(self):
        async with _client() as c:
            resp = await c.post(
                "/v1/api/coordination/run",
                json={"task": "plan then execute", "mode": "pipeline"},
            )

        assert resp.status_code == 200
        assert resp.json()["mode"] == "pipeline"

    @pytest.mark.asyncio
    async def test_run_missing_registry_returns_503(self):
        async with _client(with_registry=False) as c:
            resp = await c.post("/v1/api/coordination/run", json={"task": "x"})

        assert resp.status_code == 503
        assert "registry" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_run_missing_orchestrator_returns_503(self):
        async with _client(with_orchestrator=False) as c:
            resp = await c.post("/v1/api/coordination/run", json={"task": "x"})

        assert resp.status_code == 503
        assert "orchestrator" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_run_invalid_mode_returns_422(self):
        async with _client() as c:
            resp = await c.post(
                "/v1/api/coordination/run",
                json={"task": "x", "mode": "unknown"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_run_empty_task_returns_422(self):
        async with _client() as c:
            resp = await c.post("/v1/api/coordination/run", json={"task": ""})

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_run_engine_error_returns_500(self):
        with patch(
            "mascarade.routers.coordination.CoordinationEngine.coordinate",
            new_callable=AsyncMock,
            side_effect=RuntimeError("coordination boom"),
        ):
            async with _client() as c:
                resp = await c.post("/v1/api/coordination/run", json={"task": "x"})

        assert resp.status_code == 500
        assert "coordination boom" in resp.json()["detail"]


class TestCoordinationStatus:
    @pytest.mark.asyncio
    async def test_status_returns_saved_task(self):
        async with _client() as c:
            run_resp = await c.post("/v1/api/coordination/run", json={"task": "x"})
            task_id = run_resp.json()["task_id"]
            status_resp = await c.get(f"/v1/api/coordination/status/{task_id}")

        assert status_resp.status_code == 200
        assert status_resp.json()["task_id"] == task_id

    @pytest.mark.asyncio
    async def test_status_missing_task_returns_404(self):
        async with _client() as c:
            resp = await c.get("/v1/api/coordination/status/does-not-exist")

        assert resp.status_code == 404


class TestCoordinationAgents:
    @pytest.mark.asyncio
    async def test_agents_list_success(self):
        async with _client() as c:
            resp = await c.get("/v1/api/coordination/agents")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 4

    @pytest.mark.asyncio
    async def test_agents_filter_by_domain(self):
        async with _client() as c:
            resp = await c.get("/v1/api/coordination/agents", params={"domain": "kicad"})

        assert resp.status_code == 200
        names = {a["name"] for a in resp.json()["agents"]}
        assert names == {"kicad", "spice"}

    @pytest.mark.asyncio
    async def test_agents_filter_by_unknown_domain_returns_empty(self):
        async with _client() as c:
            resp = await c.get("/v1/api/coordination/agents", params={"domain": "unknown"})

        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_agents_filter_by_cluster(self):
        async with _client() as c:
            resp = await c.get("/v1/api/coordination/agents", params={"cluster": "code"})

        assert resp.status_code == 200
        assert [a["name"] for a in resp.json()["agents"]] == ["coder"]

    @pytest.mark.asyncio
    async def test_agents_filter_by_capability(self):
        async with _client() as c:
            resp = await c.get("/v1/api/coordination/agents", params={"capability": "pcb"})

        assert resp.status_code == 200
        assert [a["name"] for a in resp.json()["agents"]] == ["kicad"]

    @pytest.mark.asyncio
    async def test_agents_missing_registry_returns_503(self):
        async with _client(with_registry=False) as c:
            resp = await c.get("/v1/api/coordination/agents")

        assert resp.status_code == 503
        assert "registry" in resp.json()["detail"].lower()
