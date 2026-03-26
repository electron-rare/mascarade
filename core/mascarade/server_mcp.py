"""MCP-related protected routes: FreeCAD, OpenSCAD, KiCad, knowledge-base, github-dispatch, industrial."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Query

from mascarade.integrations.knowledge_base import (
    knowledge_base_auth_configured,
    knowledge_base_status_detail,
)
from mascarade.mcp import McpCallError, McpError, McpRuntimeClient, McpServerUnavailable
from mascarade.observability import new_run_id
from mascarade.server_models import (
    FreeCADCreateDocumentRequest,
    FreeCADExportDocumentRequest,
    FreeCADRunScriptRequest,
    GitHubDispatchRequest,
    GitHubDispatchStatusRequest,
    IndustrialMcpToolRequest,
    KnowledgeBaseAppendRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeScribeRequest,
    OpenSCADRenderRequest,
    OpenSCADValidateRequest,
)

if TYPE_CHECKING:
    from fastapi import APIRouter, FastAPI

logger = logging.getLogger("mascarade.server")

INDUSTRIAL_MCP_SERVER_KEYS = {"cockpit-ops", "plm", "qms", "mes", "erp", "wms", "dcs"}


def _mcp_http_exception(error: McpError) -> HTTPException:
    detail = error.structured_content.get("error") if error.structured_content else None
    code = ""
    if isinstance(detail, dict):
        code = str(detail.get("code") or "").strip()
    if not code:
        code = str(error.error_code or "").strip()

    if code == "invalid_arguments":
        status = 400
    elif code == "missing_secret":
        status = 503
    elif isinstance(error, McpServerUnavailable):
        status = 503
    else:
        status = 502

    return HTTPException(status_code=status, detail=str(error))


def _require_mcp_client(app: Any) -> McpRuntimeClient:
    if not hasattr(app.state, "mcp"):
        raise HTTPException(status_code=503, detail="MCP runtime non initialise")
    return app.state.mcp


def _require_knowledge_base(app: Any) -> McpRuntimeClient:
    if not knowledge_base_auth_configured():
        raise HTTPException(
            status_code=503,
            detail=knowledge_base_status_detail(),
        )
    return _require_mcp_client(app)


def _industrial_health_uri(server_key: str) -> str:
    if server_key == "cockpit-ops":
        return "cockpit://health"
    return f"{server_key}://health"


def _industrial_contract_uri(server_key: str) -> str | None:
    if server_key == "cockpit-ops":
        return None
    return f"{server_key}://contract"


async def _industrial_runtime_payload(client: McpRuntimeClient, server_key: str) -> dict[str, Any]:
    payload = await client.describe_server(server_key)
    health_uri = _industrial_health_uri(server_key)
    try:
        health = await client.read_resource(server_key, health_uri)
        health_payload = health.get("payload") if isinstance(health, dict) else None
        if isinstance(health_payload, dict):
            payload["health"] = health_payload
    except (McpCallError, McpServerUnavailable):
        pass

    contract_uri = _industrial_contract_uri(server_key)
    if contract_uri:
        try:
            contract = await client.read_resource(server_key, contract_uri)
            contract_payload = contract.get("payload") if isinstance(contract, dict) else None
            if isinstance(contract_payload, dict):
                payload["contract"] = contract_payload
        except (McpCallError, McpServerUnavailable):
            pass
    return payload


def register_mcp_routes(protected: APIRouter, app: FastAPI) -> None:
    """Register MCP facade routes: knowledge-base, github-dispatch, FreeCAD, OpenSCAD, industrial."""

    # --- Knowledge Base ---

    @protected.get("/knowledge-base/search")
    async def knowledge_base_search(q: str):
        if len(q) > 1000:
            raise HTTPException(status_code=400, detail="Search query too long (max 1000 chars)")
        client = _require_knowledge_base(app)
        try:
            payload = await client.knowledge_base_search(
                q,
                mode="http",
                agent_name="knowledge-base-api",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {
            "results": payload.get("results") or [],
            "provider": payload.get("provider"),
            "provider_label": payload.get("provider_label"),
        }

    @protected.get("/knowledge-base/pages/{page_id}")
    async def knowledge_base_read_page(page_id: str):
        client = _require_knowledge_base(app)
        try:
            payload = await client.knowledge_base_read_page(
                page_id,
                mode="http",
                agent_name="knowledge-base-api",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {
            "page_id": page_id,
            "content": payload.get("content") or "",
            "provider": payload.get("provider"),
            "provider_label": payload.get("provider_label"),
        }

    @protected.post("/knowledge-base/pages/{page_id}/append")
    async def knowledge_base_append(page_id: str, req: KnowledgeBaseAppendRequest):
        client = _require_knowledge_base(app)
        try:
            payload = await client.knowledge_base_append(
                page_id,
                req.content,
                mode="http",
                agent_name="knowledge-base-api",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {
            "status": "ok",
            "page_id": page_id,
            "provider": payload.get("provider"),
            "provider_label": payload.get("provider_label"),
        }

    @protected.post("/knowledge-base/pages")
    async def knowledge_base_create_page(req: KnowledgeBaseCreateRequest):
        client = _require_knowledge_base(app)
        try:
            payload = await client.knowledge_base_create_page(
                req.parent_id,
                req.title,
                req.content,
                mode="http",
                agent_name="knowledge-base-api",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {
            "page_id": payload.get("page_id") or "",
            "provider": payload.get("provider"),
            "provider_label": payload.get("provider_label"),
        }

    @protected.post("/agents/knowledge-scribe/run-and-push")
    async def run_knowledge_scribe_and_push(req: KnowledgeScribeRequest):
        try:
            agent = app.state.registry.get("knowledge-scribe")
        except KeyError:
            raise HTTPException(
                status_code=404, detail="Agent 'knowledge-scribe' not found"
            ) from None

        messages = [m.model_dump() for m in req.messages]
        prompt = messages[-1]["content"]
        context = messages[:-1] if len(messages) > 1 else None
        response = await agent.run(prompt, router=app.state.router, context=context)

        result = {
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "usage": response.usage,
            "pushed_to_knowledge_base": False,
            "run_id": req.run_id,
        }

        if req.push_to:
            client = _require_knowledge_base(app)
            trace_run_id = req.run_id or new_run_id()
            try:
                payload = await client.knowledge_base_append(
                    req.push_to,
                    response.content,
                    run_id=trace_run_id,
                    mode="knowledge-scribe",
                    step=0,
                    agent_name="knowledge-scribe",
                )
            except (McpCallError, McpServerUnavailable) as exc:
                raise _mcp_http_exception(exc) from exc
            result["pushed_to_knowledge_base"] = True
            result["knowledge_base_page_id"] = req.push_to
            result["knowledge_base_provider"] = payload.get("provider")
            result["knowledge_base_provider_label"] = payload.get("provider_label")
            result["run_id"] = trace_run_id

        return result

    # --- GitHub dispatch MCP facade ---

    @protected.get("/mcp/github-dispatch/workflows")
    async def github_dispatch_workflows():
        client = _require_mcp_client(app)
        try:
            payload = await client.github_list_allowlisted_workflows(
                mode="http",
                agent_name="github-dispatch-api",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc

        return payload

    @protected.post("/mcp/github-dispatch/dispatch")
    async def github_dispatch_dispatch(req: GitHubDispatchRequest):
        client = _require_mcp_client(app)
        try:
            payload = await client.github_dispatch_workflow(
                req.workflow_file,
                ref=req.ref,
                inputs=req.inputs,
                run_id=req.run_id,
                mode="github-dispatch",
                step=0,
                agent_name="github-dispatch",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return payload

    @protected.post("/mcp/github-dispatch/status")
    async def github_dispatch_status(req: GitHubDispatchStatusRequest):
        client = _require_mcp_client(app)
        try:
            payload = await client.github_get_dispatch_status(
                req.dispatch_id,
                run_id=req.run_id,
                mode="github-dispatch",
                step=0,
                agent_name="github-dispatch",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return payload

    # --- FreeCAD / OpenSCAD MCP facade ---

    @protected.get("/mcp/freecad/runtime")
    async def freecad_runtime_info(run_id: str | None = Query(default=None, max_length=64)):
        client = _require_mcp_client(app)
        trace_run_id = run_id or new_run_id()
        try:
            payload = await client.freecad_get_runtime_info(
                run_id=trace_run_id,
                mode="freecad",
                step=0,
                agent_name="freecad",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {**payload, "run_id": trace_run_id}

    @protected.post("/mcp/freecad/documents")
    async def freecad_create_document(req: FreeCADCreateDocumentRequest):
        client = _require_mcp_client(app)
        trace_run_id = req.run_id or new_run_id()
        try:
            payload = await client.freecad_create_document(
                req.output_path,
                name=req.name,
                primitive=req.primitive,
                length=req.length,
                width=req.width,
                height=req.height,
                run_id=trace_run_id,
                mode="freecad",
                step=0,
                agent_name="freecad",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {**payload, "run_id": trace_run_id}

    @protected.post("/mcp/freecad/export")
    async def freecad_export_document(req: FreeCADExportDocumentRequest):
        client = _require_mcp_client(app)
        trace_run_id = req.run_id or new_run_id()
        try:
            payload = await client.freecad_export_document(
                req.document_path,
                req.output_path,
                run_id=trace_run_id,
                mode="freecad",
                step=0,
                agent_name="freecad",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {**payload, "run_id": trace_run_id}

    @protected.post("/mcp/freecad/script")
    async def freecad_run_script(req: FreeCADRunScriptRequest):
        client = _require_mcp_client(app)
        trace_run_id = req.run_id or new_run_id()
        try:
            payload = await client.freecad_run_python_script(
                req.script,
                output_path=req.output_path,
                run_id=trace_run_id,
                mode="freecad",
                step=0,
                agent_name="freecad",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {**payload, "run_id": trace_run_id}

    @protected.get("/mcp/openscad/runtime")
    async def openscad_runtime_info(run_id: str | None = Query(default=None, max_length=64)):
        client = _require_mcp_client(app)
        trace_run_id = run_id or new_run_id()
        try:
            payload = await client.openscad_get_runtime_info(
                run_id=trace_run_id,
                mode="openscad",
                step=0,
                agent_name="openscad",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {**payload, "run_id": trace_run_id}

    @protected.post("/mcp/openscad/validate")
    async def openscad_validate_model(req: OpenSCADValidateRequest):
        client = _require_mcp_client(app)
        trace_run_id = req.run_id or new_run_id()
        try:
            payload = await client.openscad_validate_model(
                req.source,
                run_id=trace_run_id,
                mode="openscad",
                step=0,
                agent_name="openscad",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {**payload, "run_id": trace_run_id}

    @protected.post("/mcp/openscad/render")
    async def openscad_render_model(req: OpenSCADRenderRequest):
        client = _require_mcp_client(app)
        trace_run_id = req.run_id or new_run_id()
        try:
            payload = await client.openscad_render_model(
                req.source,
                req.output_path,
                run_id=trace_run_id,
                mode="openscad",
                step=0,
                agent_name="openscad",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {**payload, "run_id": trace_run_id}

    @protected.post("/mcp/openscad/export")
    async def openscad_export_model(req: OpenSCADRenderRequest):
        client = _require_mcp_client(app)
        trace_run_id = req.run_id or new_run_id()
        try:
            payload = await client.openscad_export_model(
                req.source,
                req.output_path,
                run_id=trace_run_id,
                mode="openscad",
                step=0,
                agent_name="openscad",
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {**payload, "run_id": trace_run_id}

    @protected.get("/mcp/industrial/servers")
    async def industrial_mcp_servers():
        client = _require_mcp_client(app)
        return {
            "items": [
                item
                for item in client.list_servers()
                if item.get("key") in INDUSTRIAL_MCP_SERVER_KEYS
            ]
        }

    @protected.get("/mcp/industrial/{server_key}/runtime")
    async def industrial_mcp_runtime(server_key: str):
        if server_key not in INDUSTRIAL_MCP_SERVER_KEYS:
            raise HTTPException(
                status_code=404, detail=f"Unknown industrial MCP server '{server_key}'"
            )
        client = _require_mcp_client(app)
        try:
            payload = await _industrial_runtime_payload(client, server_key)
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return payload

    @protected.get("/mcp/industrial/{server_key}/resource")
    async def industrial_mcp_resource(server_key: str, uri: str = Query(..., min_length=1)):
        if server_key not in INDUSTRIAL_MCP_SERVER_KEYS:
            raise HTTPException(
                status_code=404, detail=f"Unknown industrial MCP server '{server_key}'"
            )
        client = _require_mcp_client(app)
        try:
            return await client.read_resource(server_key, uri)
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc

    @protected.get("/mcp/industrial/platform")
    async def industrial_mcp_platform():
        client = _require_mcp_client(app)
        inventory = [
            item for item in client.list_servers() if item.get("key") in INDUSTRIAL_MCP_SERVER_KEYS
        ]
        runtime_results = await asyncio.gather(
            *(_industrial_runtime_payload(client, str(item.get("key", ""))) for item in inventory),
            return_exceptions=True,
        )
        servers: list[dict[str, Any]] = []
        for item, result in zip(inventory, runtime_results, strict=False):
            if isinstance(result, Exception):
                servers.append(
                    {
                        **item,
                        "ok": False,
                        "runtime_ok": False,
                        "error": str(result),
                        "tool_count": 0,
                        "resource_count": 0,
                        "prompt_count": 0,
                    }
                )
                continue
            servers.append(
                {
                    **item,
                    "ok": bool(result.get("ok", False)),
                    "runtime_ok": bool(result.get("ok", False)),
                    "protocol_version": result.get("protocol_version", ""),
                    "server_info": result.get("server_info", {}),
                    "tool_count": int(result.get("tool_count", 0) or 0),
                    "resource_count": int(result.get("resource_count", 0) or 0),
                    "prompt_count": int(result.get("prompt_count", 0) or 0),
                    **(
                        {"health": result.get("health")}
                        if isinstance(result.get("health"), dict)
                        else {}
                    ),
                    **(
                        {"contract": result.get("contract")}
                        if isinstance(result.get("contract"), dict)
                        else {}
                    ),
                }
            )

        try:
            topology = await client.read_resource("cockpit-ops", "cockpit://topology")
            topology_payload = topology.get("payload", {}) if isinstance(topology, dict) else {}
        except (McpCallError, McpServerUnavailable):
            topology_payload = {}
        try:
            vendor_contracts = await client.read_resource(
                "cockpit-ops", "cockpit://vendor-contracts"
            )
            vendor_contracts_payload = (
                vendor_contracts.get("payload", {}) if isinstance(vendor_contracts, dict) else {}
            )
        except (McpCallError, McpServerUnavailable):
            vendor_contracts_payload = {}

        return {
            "servers": servers,
            "summary": {
                "server_count": len(servers),
                "runtime_ok_count": sum(1 for item in servers if item.get("runtime_ok")),
                "runtime_error_count": sum(1 for item in servers if not item.get("runtime_ok")),
                "topology_valid": bool(topology_payload.get("valid", False)),
                "vendor_contract_ready_count": int(
                    vendor_contracts_payload.get("summary", {}).get("ready_count", 0) or 0
                ),
                "vendor_contract_blocked_count": int(
                    vendor_contracts_payload.get("summary", {}).get("blocked_count", 0) or 0
                ),
            },
            "topology": topology_payload,
            "vendor_contracts": vendor_contracts_payload,
        }

    @protected.post("/mcp/industrial/{server_key}/tools/{tool_name}")
    async def industrial_mcp_tool(server_key: str, tool_name: str, req: IndustrialMcpToolRequest):
        if server_key not in INDUSTRIAL_MCP_SERVER_KEYS:
            raise HTTPException(
                status_code=404, detail=f"Unknown industrial MCP server '{server_key}'"
            )
        client = _require_mcp_client(app)
        trace_run_id = req.run_id or new_run_id()
        try:
            payload = await client.call_tool(
                server_key,
                tool_name,
                req.arguments,
                run_id=trace_run_id,
                mode="industrial-mcp",
                step=0,
                agent_name=server_key,
            )
        except (McpCallError, McpServerUnavailable) as exc:
            raise _mcp_http_exception(exc) from exc
        return {
            "ok": not payload.is_error,
            "run_id": trace_run_id,
            "server_key": server_key,
            "tool_name": tool_name,
            "protocol_version": payload.protocol_version,
            "server_name": payload.server_name,
            "message": payload.message,
            "payload": payload.structured_content,
        }
