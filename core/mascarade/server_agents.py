"""Agent-related protected routes: CRUD, run, metrics, skills, orchestration, templates, cluster."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from fastapi import HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from mascarade.agents import Agent
from mascarade.agents.base import Gate, GateStatus
from mascarade.agents.prompt_versioning import PromptHistory, PromptVersion
from mascarade.observability import iso_utc_now
from mascarade.orchestrator.templates import WorkflowTemplate
from mascarade.server_models import (
    AgentCreate,
    AgentUpdate,
    ClusterForwardSendRequest,
    SendRequest,
    TaskRequest,
    TemplateDeployRequest,
    WorkflowTemplateCreate,
    WorkflowTemplateUpdate,
)

if TYPE_CHECKING:
    from fastapi import APIRouter, FastAPI

logger = logging.getLogger("mascarade.server")


def _hash_api_key(key: str) -> str:
    import hashlib

    if not key:
        return ""
    return hashlib.sha256(key.encode()).hexdigest()[:8]


def register_agent_routes(protected: APIRouter, app: FastAPI) -> None:
    """Register agent CRUD, run, orchestration, template, and cluster routes."""

    from mascarade.server_protected import _serialize_agent

    def _serialize_gate(gate: Gate | dict[str, object]) -> dict[str, object]:
        if isinstance(gate, dict):
            return {
                "name": str(gate.get("name") or ""),
                "description": str(gate.get("description") or ""),
                "phase": str(gate.get("phase") or "pre"),
                "required": bool(gate.get("required", True)),
                "check": str(gate.get("check") or ""),
                "status": str(gate.get("status") or "pending"),
            }
        payload = asdict(gate)
        status = payload.get("status") or "pending"
        payload["status"] = getattr(status, "value", status)
        return payload

    def _deserialize_gates(raw_gates: list[object] | None) -> list[Gate]:
        gates: list[Gate] = []
        for raw_gate in raw_gates or []:
            if hasattr(raw_gate, "model_dump"):
                raw_gate = raw_gate.model_dump()
            if isinstance(raw_gate, Gate):
                gates.append(raw_gate)
                continue
            if not isinstance(raw_gate, dict):
                continue
            gates.append(
                Gate(
                    name=str(raw_gate.get("name") or ""),
                    description=str(raw_gate.get("description") or ""),
                    phase=str(raw_gate.get("phase") or "pre"),
                    required=bool(raw_gate.get("required", True)),
                    check=str(raw_gate.get("check") or ""),
                    status=GateStatus(str(raw_gate.get("status") or "pending")),
                )
            )
        return gates

    def _serialize_template(template: WorkflowTemplate) -> dict[str, object]:
        return {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "agent_names": template.agent_names,
            "mode": template.mode.value,
            "routing_overrides": template.routing_overrides or {},
            "documentation": template.documentation,
            "builtin": app.state.template_registry.is_builtin(template.id),
        }

    def _ensure_agent_names_exist(agent_names: list[str]) -> None:
        missing = [name for name in agent_names if name not in app.state.registry]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Agent not found: {', '.join(sorted(missing))}",
            )

    # --- Agents ---

    @protected.post("/agents")
    async def create_agent(req: AgentCreate):
        agent = Agent(
            name=req.name,
            description=req.description,
            system_prompt=req.system_prompt,
            preferred_provider=req.preferred_provider,
            preferred_model=req.preferred_model,
            preferred_role=req.preferred_role,
            strategy=req.strategy,
            routing_policy=req.routing_policy,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            tools=list(req.tools),
            skills=list(req.skills),
            category=req.category,
            retry_config=req.retry_config,
            gates=_deserialize_gates(req.gates),
            evidence_refs=list(req.evidence_refs),
            capabilities=list(req.capabilities),
            cluster=req.cluster,
        )
        app.state.registry.register(agent)
        app.state.registry.save()
        return _serialize_agent(agent, app.state.registry)

    @protected.get("/agents")
    async def list_agents():
        return {
            "agents": [
                _serialize_agent(agent, app.state.registry) for agent in app.state.registry.list()
            ]
        }

    @protected.get("/agents/{name}")
    async def get_agent(name: str):
        try:
            agent = app.state.registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
        return _serialize_agent(agent, app.state.registry)

    @protected.put("/agents/{name}")
    async def update_agent(name: str, req: AgentUpdate, request: Request):
        try:
            agent = app.state.registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
        if app.state.registry.is_builtin(name):
            raise HTTPException(
                status_code=403,
                detail="Built-in agents are read-only; create a dynamic agent from the UI to edit routing.",
            )

        fields_set = set(getattr(req, "model_fields_set", set()))
        old_system_prompt = agent.system_prompt
        new_system_prompt = req.system_prompt if "system_prompt" in fields_set else agent.system_prompt
        system_prompt_changed = "system_prompt" in fields_set and old_system_prompt != new_system_prompt

        if "description" in fields_set:
            agent.description = req.description or ""
        if "system_prompt" in fields_set and req.system_prompt is not None:
            agent.system_prompt = req.system_prompt
        if "preferred_provider" in fields_set:
            agent.preferred_provider = req.preferred_provider
        if "preferred_model" in fields_set:
            agent.preferred_model = req.preferred_model
        if "preferred_role" in fields_set:
            agent.preferred_role = req.preferred_role
        if "strategy" in fields_set and req.strategy is not None:
            agent.strategy = req.strategy
        if "routing_policy" in fields_set and req.routing_policy is not None:
            agent.routing_policy = req.routing_policy
        if "temperature" in fields_set and req.temperature is not None:
            agent.temperature = req.temperature
        if "max_tokens" in fields_set and req.max_tokens is not None:
            agent.max_tokens = req.max_tokens
        if "tools" in fields_set and req.tools is not None:
            agent.tools = list(req.tools)
        if "skills" in fields_set and req.skills is not None:
            agent.skills = list(req.skills)
        if "category" in fields_set:
            agent.category = req.category
        if "retry_config" in fields_set:
            agent.retry_config = req.retry_config
        if "gates" in fields_set and req.gates is not None:
            agent.gates = _deserialize_gates(req.gates)
        if "evidence_refs" in fields_set and req.evidence_refs is not None:
            agent.evidence_refs = list(req.evidence_refs)
        if "capabilities" in fields_set and req.capabilities is not None:
            agent.capabilities = list(req.capabilities)
        if "cluster" in fields_set:
            agent.cluster = req.cluster

        # Create version if system_prompt changed
        if system_prompt_changed:
            # Get API key from request headers for author tracking
            auth_header = request.headers.get("Authorization", "")
            api_key = ""
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:]
            author_hash = _hash_api_key(api_key)

            # Create PromptHistory and load existing versions
            prompt_history = PromptHistory(storage_path=None)
            prompt_history._versions = [PromptVersion(**v) for v in agent.prompt_versions]

            # Add new version
            prompt_history.add_version(
                content=agent.system_prompt,
                author_hash=author_hash,
                note=req.version_note,
            )

            # Update agent's prompt_versions
            agent.prompt_versions = [asdict(v) for v in prompt_history._versions]

        app.state.registry.save()
        return _serialize_agent(agent, app.state.registry)

    @protected.delete("/agents/{name}")
    async def delete_agent(name: str):
        try:
            app.state.registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
        if app.state.registry.is_builtin(name):
            raise HTTPException(
                status_code=403,
                detail="Built-in agents are read-only and cannot be deleted.",
            )

        app.state.registry.remove(name)
        app.state.registry.save()
        return {"message": f"Agent '{name}' deleted successfully"}

    @protected.post("/agents/{name}/run")
    async def run_agent(name: str, req: SendRequest):
        if not req.messages:
            raise HTTPException(status_code=400, detail="At least one message is required")

        try:
            agent = app.state.registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None

        messages = [m.model_dump() for m in req.messages]
        prompt = messages[-1]["content"]
        context = messages[:-1] if len(messages) > 1 else None
        response = await agent.run(prompt, router=app.state.router, context=context)
        return {
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
        }

    @protected.get("/agents/{name}/metrics")
    async def get_agent_metrics(name: str):
        try:
            app.state.registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
        return app.state.registry.agent_metrics(name)

    @protected.get("/agents/{name}/prompts/history")
    async def prompt_history(name: str):
        try:
            agent = app.state.registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
        return {"versions": list(agent.prompt_versions or [])}

    @protected.post("/agents/{name}/prompts/rollback/{version}")
    async def rollback_prompt(name: str, version: int):
        try:
            agent = app.state.registry.get(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent '{name}' not found") from None
        if app.state.registry.is_builtin(name):
            raise HTTPException(
                status_code=403,
                detail="Built-in agents are read-only; create a dynamic agent from the UI to edit routing.",
            )
        if version < 1:
            raise HTTPException(status_code=400, detail=f"Invalid version: {version}")

        target_version = next(
            (entry for entry in agent.prompt_versions if entry.get("version_number") == version),
            None,
        )
        if target_version is None:
            raise HTTPException(status_code=400, detail=f"Invalid version: {version}")

        previous_prompt = agent.system_prompt
        agent.system_prompt = str(target_version["content"])
        rollback_entry = {
            "version_number": len(agent.prompt_versions) + 1,
            "timestamp": iso_utc_now(),
            "content": previous_prompt,
            "author_hash": "system",
            "diff": None,
            "note": f"Rollback to version {version}",
        }
        agent.prompt_versions.append(rollback_entry)
        app.state.registry.save()
        return {
            "message": f"Rolled back to version {version}",
            "current_prompt": agent.system_prompt,
            "versions": list(agent.prompt_versions),
        }

    # --- Orchestration ---

    @protected.post("/orchestrate")
    async def orchestrate(req: TaskRequest):
        try:
            run = await app.state.orchestrator.run(
                req.agent_names,
                req.prompt,
                mode=req.mode,
                routing_overrides={
                    agent_name: override.model_dump()
                    for agent_name, override in req.routing_overrides.items()
                },
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Agent not found: {exc}") from exc
        return {
            "run_id": run.run_id,
            "mode": run.mode.value,
            "results": [
                {
                    "agent": r.agent_name,
                    "step": r.step,
                    "content": r.response.content,
                    "model": r.response.model,
                    "provider": r.response.provider,
                    "remote": r.remote,
                    "selected_by": r.selected_by,
                    "peer_id": r.peer_id,
                    "node_id": r.node_id,
                    "role": r.role,
                    **({"error": r.error} if r.error else {}),
                }
                for r in run.results
            ],
        }

    @protected.get("/orchestrate/templates")
    async def list_templates():
        """List all available workflow templates."""
        templates = app.state.template_registry.list()
        return {"templates": [_serialize_template(template) for template in templates]}

    @protected.post("/orchestrate/templates")
    async def create_template(req: WorkflowTemplateCreate):
        if req.id in app.state.template_registry:
            raise HTTPException(status_code=409, detail=f"Template '{req.id}' already exists")
        _ensure_agent_names_exist(req.agent_names)
        template = WorkflowTemplate(
            id=req.id,
            name=req.name,
            description=req.description,
            agent_names=list(req.agent_names),
            mode=req.mode,
            routing_overrides={
                agent_name: override.model_dump()
                for agent_name, override in req.routing_overrides.items()
            }
            or None,
            documentation=req.documentation,
        )
        app.state.template_registry.register(template)
        app.state.template_registry.save()
        return _serialize_template(template)

    @protected.get("/orchestrate/templates/{template_id}")
    async def get_template(template_id: str):
        """Get a specific workflow template by ID."""
        try:
            template = app.state.template_registry.get(template_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Template not found: {template_id}"
            ) from exc
        return _serialize_template(template)

    @protected.put("/orchestrate/templates/{template_id}")
    async def update_template(template_id: str, req: WorkflowTemplateUpdate):
        try:
            template = app.state.template_registry.get(template_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Template not found: {template_id}"
            ) from exc
        if app.state.template_registry.is_builtin(template_id):
            raise HTTPException(
                status_code=403,
                detail="Built-in templates are read-only and cannot be edited.",
            )

        fields_set = set(getattr(req, "model_fields_set", set()))
        if "agent_names" in fields_set and req.agent_names is not None:
            _ensure_agent_names_exist(req.agent_names)
            template.agent_names = list(req.agent_names)
        if "name" in fields_set and req.name is not None:
            template.name = req.name
        if "description" in fields_set and req.description is not None:
            template.description = req.description
        if "mode" in fields_set and req.mode is not None:
            template.mode = req.mode
        if "routing_overrides" in fields_set:
            template.routing_overrides = (
                {
                    agent_name: override.model_dump()
                    for agent_name, override in (req.routing_overrides or {}).items()
                }
                or None
            )
        if "documentation" in fields_set and req.documentation is not None:
            template.documentation = req.documentation

        app.state.template_registry.save()
        return _serialize_template(template)

    @protected.delete("/orchestrate/templates/{template_id}")
    async def delete_template(template_id: str):
        try:
            app.state.template_registry.get(template_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Template not found: {template_id}"
            ) from exc
        if app.state.template_registry.is_builtin(template_id):
            raise HTTPException(
                status_code=403,
                detail="Built-in templates are read-only and cannot be deleted.",
            )
        app.state.template_registry.remove(template_id)
        app.state.template_registry.save()
        return {"message": f"Template '{template_id}' deleted successfully"}

    @protected.post("/orchestrate/templates/{template_id}/deploy")
    async def deploy_template(template_id: str, req: TemplateDeployRequest):
        """Deploy a workflow template with user input."""
        try:
            template = app.state.template_registry.get(template_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=404, detail=f"Template not found: {template_id}"
            ) from exc

        # Merge template routing_overrides with request overrides (request takes precedence)
        routing_overrides = {}
        if template.routing_overrides:
            routing_overrides.update(template.routing_overrides)
        if req.routing_overrides:
            routing_overrides.update(
                {
                    agent_name: override.model_dump()
                    for agent_name, override in req.routing_overrides.items()
                }
            )

        try:
            run = await app.state.orchestrator.run(
                template.agent_names,
                req.input,
                mode=template.mode,
                routing_overrides=routing_overrides,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Agent not found: {exc}") from exc

        return {
            "run_id": run.run_id,
            "template_id": template_id,
            "mode": run.mode.value,
            "results": [
                {
                    "agent": r.agent_name,
                    "step": r.step,
                    "content": r.response.content,
                    "model": r.response.model,
                    "provider": r.response.provider,
                    "remote": r.remote,
                    "selected_by": r.selected_by,
                    "peer_id": r.peer_id,
                    "node_id": r.node_id,
                    "role": r.role,
                    **({"error": r.error} if r.error else {}),
                }
                for r in run.results
            ],
        }

    # --- Cluster / multi-node ---

    @protected.get("/cluster/identity")
    async def cluster_identity():
        return app.state.cluster.local_identity().to_dict()

    @protected.get("/cluster/peers")
    async def cluster_peers():
        peers = await app.state.cluster.probe_peers()
        return {
            "node": app.state.cluster.local_identity().to_dict(),
            "peers": [peer.to_dict() for peer in peers],
        }

    @protected.post("/cluster/forward/send")
    async def cluster_forward_send(req: ClusterForwardSendRequest):
        payload = req.model_dump(exclude={"peer_id", "preferred_role", "allow_local"})
        return await app.state.cluster.forward_send(
            peer_id=req.peer_id,
            preferred_role=req.preferred_role,
            allow_local=req.allow_local,
            payload=payload,
        )

    # --- Orchestration traces ---

    @protected.get("/agent-traces/recent")
    async def recent_agent_traces(
        limit: int = Query(default=50, ge=1, le=500),
        run_id: str | None = Query(default=None, max_length=64),
        agent_name: str | None = Query(default=None, max_length=128),
        event_type: str | None = Query(default=None, max_length=64),
    ):
        events = app.state.trace_buffer.recent(
            limit=limit,
            run_id=run_id,
            agent_name=agent_name,
            event_type=event_type,
        )
        return {
            "events": [event.to_dict() for event in events],
            "count": len(events),
        }

    @protected.get("/agent-traces/stream")
    async def stream_agent_traces(
        request: Request,
        run_id: str | None = Query(default=None, max_length=64),
        agent_name: str | None = Query(default=None, max_length=128),
        event_type: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=20, ge=0, le=200),
    ):
        async def event_stream():
            queue, unsubscribe = app.state.trace_buffer.subscribe(
                run_id=run_id,
                agent_name=agent_name,
                event_type=event_type,
            )
            try:
                if limit > 0:
                    for event in app.state.trace_buffer.recent(
                        limit=limit,
                        run_id=run_id,
                        agent_name=agent_name,
                        event_type=event_type,
                    ):
                        yield f"event: agent_trace\ndata: {json.dumps(event.to_dict())}\n\n"

                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15)
                    except TimeoutError:
                        yield f"event: heartbeat\ndata: {json.dumps({'ts': iso_utc_now()})}\n\n"
                        continue
                    yield f"event: agent_trace\ndata: {json.dumps(event.to_dict())}\n\n"
            finally:
                unsubscribe()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @protected.get("/agent-traces/{run_id}")
    async def run_agent_traces(
        run_id: str,
        limit: int = Query(default=200, ge=1, le=1000),
    ):
        events = app.state.trace_buffer.run_events(run_id, limit=limit)
        return {
            "run_id": run_id,
            "events": [event.to_dict() for event in events],
            "count": len(events),
        }
