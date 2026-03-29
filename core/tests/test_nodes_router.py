"""HTTP route tests for the Node Catalog API (mascarade.routers.nodes).

Covers all 5 routes via FastAPI TestClient with mocked NodeStore and no-op auth:
  GET  /v1/nodes/catalog
  POST /v1/nodes/register
  GET  /v1/nodes/{node_id}
  DELETE /v1/nodes/{node_id}
  GET  /v1/nodes/domains/list
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mascarade.auth import require_auth
from mascarade.node_engine.runtime import ExecutionMode
from mascarade.node_engine.store import NodeMetadata, NodeStore
from mascarade.routers.nodes import get_node_store, router

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_metadata(**kwargs) -> NodeMetadata:
    """Build a NodeMetadata with sensible defaults, overridable via kwargs."""
    defaults = {
        "node_id": "node-001",
        "name": "Test Node",
        "domain": "audio",
        "description": "A test node",
        "version": "1.0.0",
        "tags": ["test"],
        "capabilities": {"input": "pcm"},
    }
    defaults.update(kwargs)
    return NodeMetadata(**defaults)


@pytest.fixture()
def mock_store() -> MagicMock:
    """Mock NodeStore with default empty state."""
    store = MagicMock(spec=NodeStore)
    store.list_all_nodes.return_value = []
    store.list_nodes_by_domain.return_value = []
    store.get_node.return_value = None
    store.unregister_node.return_value = False
    store.get_domain_list.return_value = []
    return store


@pytest.fixture()
def client(mock_store: MagicMock):
    """TestClient with bypassed auth and injected mock store."""
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[require_auth] = lambda: None
    app.dependency_overrides[get_node_store] = lambda: mock_store

    with TestClient(app) as tc:
        yield tc, mock_store

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /v1/nodes/catalog
# ---------------------------------------------------------------------------


class TestGetCatalog:
    def test_catalog_empty(self, client):
        tc, store = client
        store.list_all_nodes.return_value = []

        resp = tc.get("/v1/nodes/catalog")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["nodes"] == []
        assert data["domain"] is None

    def test_catalog_returns_nodes(self, client):
        tc, store = client
        node = _make_metadata()
        store.list_all_nodes.return_value = [node]

        resp = tc.get("/v1/nodes/catalog")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["nodes"][0]["node_id"] == "node-001"
        assert data["nodes"][0]["domain"] == "audio"

    def test_catalog_filtered_by_domain(self, client):
        tc, store = client
        node = _make_metadata(node_id="v-001", domain="vision")
        store.list_nodes_by_domain.return_value = [node]

        resp = tc.get("/v1/nodes/catalog?domain=vision")

        assert resp.status_code == 200
        data = resp.json()
        assert data["domain"] == "vision"
        assert data["total"] == 1
        assert data["nodes"][0]["node_id"] == "v-001"
        store.list_nodes_by_domain.assert_called_once_with("vision")

    def test_catalog_domain_filter_empty(self, client):
        tc, store = client
        store.list_nodes_by_domain.return_value = []

        resp = tc.get("/v1/nodes/catalog?domain=unknown")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["nodes"] == []


# ---------------------------------------------------------------------------
# POST /v1/nodes/register
# ---------------------------------------------------------------------------


class TestRegisterNode:
    def test_register_success(self, client):
        tc, store = client
        payload = {
            "node_id": "node-new",
            "name": "My Node",
            "domain": "text",
            "description": "does stuff",
            "version": "2.0.0",
            "tags": ["nlp"],
            "capabilities": {"lang": "fr"},
        }

        resp = tc.post("/v1/nodes/register", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["node_id"] == "node-new"
        store.register_node.assert_called_once()

    def test_register_minimal_fields(self, client):
        tc, store = client
        payload = {"node_id": "min-node", "name": "Min", "domain": "text"}

        resp = tc.post("/v1/nodes/register", json=payload)

        assert resp.status_code == 200
        assert resp.json()["node_id"] == "min-node"

    def test_register_missing_required_field(self, client):
        tc, _ = client
        # Missing 'domain' which is required
        payload = {"node_id": "bad", "name": "Bad"}

        resp = tc.post("/v1/nodes/register", json=payload)

        assert resp.status_code == 422

    def test_register_store_error_returns_400(self, client):
        tc, store = client
        store.register_node.side_effect = ValueError("duplicate node")
        payload = {"node_id": "dup", "name": "Dup", "domain": "audio"}

        resp = tc.post("/v1/nodes/register", json=payload)

        assert resp.status_code == 400
        assert "Registration failed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /v1/nodes/{node_id}
# ---------------------------------------------------------------------------


class TestGetNode:
    def test_get_existing_node(self, client):
        tc, store = client
        node = _make_metadata(node_id="found-001", name="Found Node")
        store.get_node.return_value = node

        resp = tc.get("/v1/nodes/found-001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["node_id"] == "found-001"
        assert data["name"] == "Found Node"

    def test_get_missing_node_returns_404(self, client):
        tc, store = client
        store.get_node.return_value = None

        resp = tc.get("/v1/nodes/nonexistent")

        assert resp.status_code == 404
        assert "nonexistent" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# DELETE /v1/nodes/{node_id}
# ---------------------------------------------------------------------------


class TestUnregisterNode:
    def test_delete_existing_node(self, client):
        tc, store = client
        store.unregister_node.return_value = True

        resp = tc.delete("/v1/nodes/node-001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "node-001" in data["message"]

    def test_delete_missing_node_returns_404(self, client):
        tc, store = client
        store.unregister_node.return_value = False

        resp = tc.delete("/v1/nodes/ghost-node")

        assert resp.status_code == 404
        assert "ghost-node" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /v1/nodes/domains/list
# ---------------------------------------------------------------------------


class TestGetDomains:
    def test_domains_empty(self, client):
        tc, store = client
        store.get_domain_list.return_value = []

        resp = tc.get("/v1/nodes/domains/list")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["domains"] == []

    def test_domains_several(self, client):
        tc, store = client
        store.get_domain_list.return_value = ["audio", "vision", "text"]

        resp = tc.get("/v1/nodes/domains/list")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert set(data["domains"]) == {"audio", "vision", "text"}


# ---------------------------------------------------------------------------
# POST /v1/nodes/graphs/execute
# ---------------------------------------------------------------------------


class TestExecuteGraph:
    @patch("mascarade.node_engine.executor.GraphExecutor")
    def test_execute_graph_success(self, mock_executor_cls, client):
        tc, _ = client

        fake_record = SimpleNamespace(
            node_id="n1",
            status="completed",
            outputs={"out": "ok"},
            error=None,
            error_type=None,
            execution_time_ms=3.2,
        )
        fake_result = SimpleNamespace(
            graph_id="g-1",
            status="completed",
            outputs={"n1": {"out": "ok"}},
            error=None,
            node_records=[fake_record],
            total_time_ms=8.5,
        )

        mock_executor = MagicMock()
        mock_executor.execute_graph = AsyncMock(return_value=fake_result)
        mock_executor_cls.return_value = mock_executor

        payload = {
            "graph_id": "g-1",
            "name": "demo",
            "nodes": [{"id": "n1", "node_type": "audio.transcribe", "config": {}}],
            "edges": [],
            "mode": "eager",
        }

        resp = tc.post("/v1/nodes/graphs/execute", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["graph_id"] == "g-1"
        assert data["status"] == "completed"
        assert data["outputs"]["n1"]["out"] == "ok"
        assert data["node_records"][0]["node_id"] == "n1"

    @patch("mascarade.node_engine.executor.GraphExecutor")
    def test_execute_graph_passes_lazy_targets_and_timeout(self, mock_executor_cls, client):
        tc, _ = client

        fake_result = SimpleNamespace(
            graph_id="g-lazy",
            status="completed",
            outputs={},
            error=None,
            node_records=[],
            total_time_ms=1.0,
        )
        mock_executor = MagicMock()
        mock_executor.execute_graph = AsyncMock(return_value=fake_result)
        mock_executor_cls.return_value = mock_executor

        payload = {
            "graph_id": "g-lazy",
            "nodes": [
                {"id": "n1", "node_type": "audio.transcribe", "config": {}},
                {"id": "n2", "node_type": "audio.transcribe", "config": {}},
            ],
            "edges": [
                {
                    "id": "e1",
                    "source_node": "n1",
                    "source_port": "out",
                    "target_node": "n2",
                    "target_port": "in",
                }
            ],
            "mode": "lazy",
            "target_nodes": ["n2"],
            "timeout_seconds": 12.5,
        }

        resp = tc.post("/v1/nodes/graphs/execute", json=payload)

        assert resp.status_code == 200
        kwargs = mock_executor.execute_graph.call_args.kwargs
        assert kwargs["mode"] == ExecutionMode.LAZY
        assert kwargs["target_nodes"] == {"n2"}
        assert kwargs["timeout_seconds"] == 12.5

    def test_execute_graph_nodes_empty_returns_400(self, client):
        tc, _ = client

        payload = {
            "graph_id": "g-empty",
            "nodes": [],
            "edges": [],
            "mode": "eager",
        }

        resp = tc.post("/v1/nodes/graphs/execute", json=payload)

        assert resp.status_code == 400
        assert "at least one node" in resp.json()["detail"].lower()

    def test_execute_graph_edge_references_unknown_node_returns_400(self, client):
        tc, _ = client

        payload = {
            "graph_id": "g-bad-edge",
            "nodes": [{"id": "n1", "node_type": "audio.transcribe", "config": {}}],
            "edges": [
                {
                    "id": "e1",
                    "source_node": "n1",
                    "source_port": "out",
                    "target_node": "n999",
                    "target_port": "in",
                }
            ],
            "mode": "eager",
        }

        resp = tc.post("/v1/nodes/graphs/execute", json=payload)

        assert resp.status_code == 400
        assert "unknown nodes" in resp.json()["detail"].lower()

    def test_execute_graph_unknown_target_nodes_returns_400(self, client):
        tc, _ = client

        payload = {
            "graph_id": "g-bad-target",
            "nodes": [{"id": "n1", "node_type": "audio.transcribe", "config": {}}],
            "edges": [],
            "mode": "lazy",
            "target_nodes": ["n404"],
        }

        resp = tc.post("/v1/nodes/graphs/execute", json=payload)

        assert resp.status_code == 400
        assert "unknown ids" in resp.json()["detail"].lower()

    @patch("mascarade.node_engine.executor.GraphExecutor")
    def test_execute_graph_serializes_node_record_fields(self, mock_executor_cls, client):
        tc, _ = client

        fake_record = SimpleNamespace(
            node_id="n1",
            status="failed",
            outputs={},
            error="No worker",
            error_type="RuntimeError",
            execution_time_ms=2.7,
        )
        fake_result = SimpleNamespace(
            graph_id="g-fail",
            status="failed",
            outputs={},
            error="No worker",
            node_records=[fake_record],
            total_time_ms=3.0,
        )
        mock_executor = MagicMock()
        mock_executor.execute_graph = AsyncMock(return_value=fake_result)
        mock_executor_cls.return_value = mock_executor

        payload = {
            "graph_id": "g-fail",
            "nodes": [{"id": "n1", "node_type": "audio.transcribe", "config": {}}],
            "edges": [],
            "mode": "eager",
        }

        resp = tc.post("/v1/nodes/graphs/execute", json=payload)

        assert resp.status_code == 200
        record = resp.json()["node_records"][0]
        assert record["status"] == "failed"
        assert record["error_type"] == "RuntimeError"
        assert record["execution_time_ms"] == 2.7

    def test_execute_graph_invalid_mode_returns_400(self, client):
        tc, _ = client

        payload = {
            "graph_id": "g-2",
            "nodes": [],
            "edges": [],
            "mode": "invalid-mode",
        }

        resp = tc.post("/v1/nodes/graphs/execute", json=payload)

        assert resp.status_code == 400
        assert "Invalid mode" in resp.json()["detail"]

    @patch("mascarade.node_engine.executor.GraphExecutor")
    def test_execute_graph_runtime_error_returns_500(self, mock_executor_cls, client):
        tc, _ = client

        mock_executor = MagicMock()
        mock_executor.execute_graph = AsyncMock(side_effect=RuntimeError("boom"))
        mock_executor_cls.return_value = mock_executor

        payload = {
            "graph_id": "g-3",
            "nodes": [{"id": "n1", "node_type": "audio.transcribe", "config": {}}],
            "edges": [],
            "mode": "eager",
        }

        resp = tc.post("/v1/nodes/graphs/execute", json=payload)

        assert resp.status_code == 500
        assert "Graph execution failed" in resp.json()["detail"]
