"""StateGraph API — invoke, stream, and checkpoint endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from mascarade.auth import require_auth
from mascarade.orchestrator.state_graph import StateGraph

logger = logging.getLogger("mascarade.routers.graph")

router = APIRouter(prefix="/v1/graph", dependencies=[Depends(require_auth)], tags=["graph"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class GraphNodeDef(BaseModel):
    name: str
    agent: str | None = None
    prompt_template: str | None = None


class GraphEdgeDef(BaseModel):
    source: str
    target: str


class ConditionalEdgeDef(BaseModel):
    source: str
    condition_key: str = Field(
        ...,
        description="State key whose value is used to pick the next node",
    )
    mapping: dict[str, str] = Field(
        ...,
        description="Map from condition value to target node name (use '__end__' for END)",
    )


class GraphDefinition(BaseModel):
    nodes: list[GraphNodeDef]
    edges: list[GraphEdgeDef] = Field(default_factory=list)
    conditional_edges: list[ConditionalEdgeDef] = Field(default_factory=list)
    entry_point: str
    finish_points: list[str] = Field(default_factory=list)


class InvokeRequest(BaseModel):
    graph: GraphDefinition
    state: dict[str, Any]
    config: dict[str, Any] | None = None
    run_id: str | None = None
    resume: bool = False


class InvokeResponse(BaseModel):
    run_id: str
    state: dict[str, Any]


class StreamRequest(BaseModel):
    graph: GraphDefinition
    state: dict[str, Any]
    run_id: str | None = None


# ---------------------------------------------------------------------------
# Graph builder from definition
# ---------------------------------------------------------------------------


def _build_graph(
    definition: GraphDefinition,
    request: Request,
) -> StateGraph:
    """Construct a StateGraph from a GraphDefinition payload."""
    sg = StateGraph()

    for node_def in definition.nodes:
        agent_name = node_def.agent
        prompt_tpl = node_def.prompt_template

        if agent_name:
            # Build a node function that calls the named agent via the router
            async def _agent_node(
                state: dict[str, Any],
                _agent=agent_name,
                _tpl=prompt_tpl,
            ) -> dict[str, Any]:
                orch_router = getattr(request.app.state, "router", None)
                registry = getattr(request.app.state, "registry", None)
                if orch_router is None or registry is None:
                    raise RuntimeError("Router/registry not available on app state")
                agent = registry.get(_agent)
                prompt = _tpl.format(**state) if _tpl else json.dumps(state)
                response = await orch_router.send(
                    [{"role": "user", "content": prompt}],
                    system=getattr(agent, "system_prompt", None),
                    temperature=getattr(agent, "temperature", 0.7),
                    max_tokens=getattr(agent, "max_tokens", 2048),
                )
                return {"last_response": response.content, f"{_agent}_output": response.content}

            sg.add_node(node_def.name, _agent_node)
        else:
            # Pass-through node (useful for routing-only nodes)
            sg.add_node(node_def.name, lambda state: {})

    for edge in definition.edges:
        sg.add_edge(edge.source, edge.target)

    for ce in definition.conditional_edges:
        key = ce.condition_key

        def _condition(state: dict[str, Any], _key: str = key) -> str:
            return str(state.get(_key, ""))

        sg.add_conditional_edges(ce.source, _condition, ce.mapping)

    sg.set_entry_point(definition.entry_point)
    for fp in definition.finish_points:
        sg.set_finish_point(fp)

    return sg


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/invoke", response_model=InvokeResponse)
async def invoke_graph(body: InvokeRequest, request: Request) -> InvokeResponse:
    """Run a graph definition with the given initial state."""
    run_id = body.run_id or uuid.uuid4().hex
    try:
        sg = _build_graph(body.graph, request)
        result = await sg.invoke(
            body.state,
            config=body.config,
            run_id=run_id,
            resume=body.resume,
        )
    except Exception as exc:
        logger.exception("Graph invoke failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return InvokeResponse(run_id=run_id, state=result)


@router.post("/stream")
async def stream_graph(body: StreamRequest, request: Request) -> StreamingResponse:
    """SSE stream of ``(node_name, state)`` as the graph executes."""
    run_id = body.run_id or uuid.uuid4().hex

    async def _sse_generator():
        try:
            sg = _build_graph(body.graph, request)
            async for node_name, state in sg.stream(body.state, run_id=run_id):
                payload = json.dumps({"node": node_name, "state": state}, default=str)
                yield f"data: {payload}\n\n"
            yield f"data: {json.dumps({'node': '__end__', 'state': {}})}\n\n"
        except Exception as exc:
            error_payload = json.dumps({"error": str(exc)})
            yield f"data: {error_payload}\n\n"

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Run-Id": run_id},
    )


@router.get("/checkpoints/{run_id}")
async def get_checkpoint(run_id: str) -> dict[str, Any]:
    """Retrieve the latest checkpoint for a given run."""
    sg = StateGraph(checkpoint_dir="/tmp/mascarade_graph_checkpoints")
    checkpoint = sg.load_checkpoint(run_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail=f"No checkpoint for run '{run_id}'")
    return checkpoint
