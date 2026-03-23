"""Node Engine API — graph CRUD and execution endpoints."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.node_engine.graph import Graph, GraphEdge, GraphNode
from mascarade.node_engine.persistence import GraphSerializer
from mascarade.node_engine.runtime import GraphRuntime
from mascarade.node_engine.workers.ai.register import register_ai_worker

logger = logging.getLogger("mascarade.routers.node_engine")

router = APIRouter(prefix="/api/node-engine", tags=["node-engine"])

# Module-level runtime — initialized lazily on first use
_runtime: GraphRuntime | None = None
_serializer = GraphSerializer()


def _get_runtime(request: Request) -> GraphRuntime:
    """Get or create the GraphRuntime, wiring it to app-level services."""
    global _runtime
    if _runtime is not None:
        return _runtime

    _runtime = GraphRuntime()
    register_ai_worker(
        _runtime,
        router=getattr(request.app.state, "router", None),
        registry=getattr(request.app.state, "registry", None),
        orchestrator=getattr(request.app.state, "orchestrator", None),
    )
    logger.info("GraphRuntime initialized with AI worker")
    return _runtime


def _serialize_execution_context(graph_id: str, ctx) -> dict[str, Any]:
    """Serialize a GraphExecutionContext to a JSON-safe dict."""
    return {
        "graph_id": graph_id,
        "status": ctx.status.value if hasattr(ctx.status, "value") else str(ctx.status),
        "results": {
            node_id: {
                "node_id": nr.node_id,
                "status": (
                    nr.status.value if hasattr(nr.status, "value") else str(nr.status)
                ),
                "outputs": nr.outputs,
                "error": nr.error,
                "worker": nr.worker_name,
                "execution_time_ms": nr.execution_time_ms,
            }
            for node_id, nr in ctx.node_results.items()
        },
    }


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class GraphCreateRequest(BaseModel):
    name: str
    description: str = ""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class GraphExecuteRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/graphs/{graph_id}/execute")
async def execute_graph(graph_id: str, body: GraphExecuteRequest, request: Request):
    """Execute a saved graph through the Node Engine runtime."""
    runtime = _get_runtime(request)

    # Load graph from persistence
    try:
        graph = _serializer.load(f"data/node-engine/graphs/{graph_id}.json")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Graph '{graph_id}' not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load graph: {exc}")

    # Validate
    errors = await runtime.validate_graph(graph)
    if errors:
        raise HTTPException(status_code=422, detail={"validation_errors": errors})

    # Execute
    try:
        ctx = await runtime.execute(graph, initial_inputs=body.inputs)
        return _serialize_execution_context(graph_id, ctx)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Graph execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Execution failed: {exc}")


@router.post("/graphs/execute-inline")
async def execute_inline_graph(body: GraphCreateRequest, request: Request):
    """Execute a graph definition directly without saving it first."""
    runtime = _get_runtime(request)

    # Build graph from request
    graph = Graph(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
    )

    for node_data in body.nodes:
        graph.add_node(GraphNode(**node_data))

    for edge_data in body.edges:
        graph.add_edge(GraphEdge(**edge_data))

    # Validate
    errors = await runtime.validate_graph(graph)
    if errors:
        raise HTTPException(status_code=422, detail={"validation_errors": errors})

    # Execute
    try:
        ctx = await runtime.execute(graph)
        return _serialize_execution_context(graph.id, ctx)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Inline graph execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Execution failed: {exc}")


@router.get("/runtime/status")
async def runtime_status(request: Request):
    """Return node engine runtime status and registered workers."""
    runtime = _get_runtime(request)
    workers = runtime.list_workers()
    return {
        "status": "running",
        "workers": workers,
    }
