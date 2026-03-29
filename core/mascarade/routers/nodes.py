"""Node Catalog API — DAG node discovery and registration endpoints.


Exposes:
  GET /v1/nodes/catalog         — List all registered nodes (optionally filtered by domain)
  POST /v1/nodes/register       — Register a new node
  GET /v1/nodes/{node_id}       — Get node metadata
  DELETE /v1/nodes/{node_id}    — Unregister a node
  GET /v1/nodes/domains         — List all registered domains
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from mascarade.auth import require_auth
from mascarade.config import settings
from mascarade.node_engine.store import NodeMetadata, NodeStore

logger = logging.getLogger("mascarade.routers.nodes")

# Global node store instance (initialized with Redis)
_node_store: NodeStore | None = None


def get_node_store() -> NodeStore:
    """Lazily initialize and return the global node store."""
    global _node_store
    if _node_store is None:
        try:
            redis_url = settings.redis_url or "redis://localhost:6379/0"
            _node_store = NodeStore(redis_url=redis_url)
            logger.info("Initialized NodeStore with Redis")
        except Exception as e:
            logger.error(f"Failed to initialize NodeStore: {e}")
            raise HTTPException(
                status_code=503,
                detail="Node store initialization failed. Check Redis connectivity."
            ) from e
    return _node_store


# API Router with authentication
router = APIRouter(
    prefix="/v1/nodes",
    dependencies=[Depends(require_auth)],
    tags=["nodes"]
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class NodeRegistrationRequest(BaseModel):
    """Request to register a new node."""

    node_id: str = Field(..., description="Unique node identifier")
    name: str = Field(..., description="Human-readable node name")
    domain: str = Field(..., description="Domain (audio, vision, text, etc.)")
    description: str | None = Field(None, description="Node description")
    version: str = Field(default="1.0.0", description="Node version")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    capabilities: dict = Field(default_factory=dict, description="Node capabilities")


class CatalogResponse(BaseModel):
    """Response containing catalog information."""

    total: int = Field(..., description="Total number of nodes")
    domain: str | None = Field(None, description="Domain filter applied (if any)")
    nodes: list[NodeMetadata] = Field(..., description="List of nodes")


class DomainsResponse(BaseModel):
    """Response containing list of registered domains."""

    domains: list[str] = Field(..., description="List of domain names")
    total: int = Field(..., description="Total number of domains")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/catalog")
async def get_catalog(
    domain: str | None = Query(None, description="Filter by domain (optional)"),
    store: NodeStore = Depends(get_node_store),
) -> CatalogResponse:
    """
    Get the node catalog, optionally filtered by domain.

    Query Parameters:
    - domain: Optional domain filter (e.g., "audio", "vision", "text")

    Returns:
    - total: Total number of nodes
    - domain: The domain filter applied (if any)
    - nodes: Array of registered nodes

    Example:
        GET /v1/nodes/catalog?domain=audio
    """
    try:
        if domain:
            nodes = store.list_nodes_by_domain(domain)
        else:
            nodes = store.list_all_nodes()

        return CatalogResponse(
            total=len(nodes),
            domain=domain,
            nodes=nodes
        )
    except Exception as e:
        logger.error(f"Error fetching catalog: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch catalog") from e


@router.post("/register")
async def register_node(
    req: NodeRegistrationRequest,
    store: NodeStore = Depends(get_node_store),
) -> dict:
    """
    Register a new node in the catalog.

    Request Body:
    - node_id: Unique identifier (required)
    - name: Human-readable name (required)
    - domain: Domain category (required)
    - description: Optional description
    - version: Version string (default: "1.0.0")
    - tags: Optional list of tags
    - capabilities: Optional capabilities dict

    Returns:
    - status: "ok" if successful
    - message: Success message with node ID
    - node_id: The registered node ID
    """
    try:
        metadata = NodeMetadata(
            node_id=req.node_id,
            name=req.name,
            domain=req.domain,
            description=req.description,
            version=req.version,
            tags=req.tags,
            capabilities=req.capabilities,
        )
        store.register_node(metadata)
        return {
            "status": "ok",
            "message": f"Node registered: {req.node_id}",
            "node_id": req.node_id,
        }
    except Exception as e:
        logger.error(f"Error registering node: {e}")
        raise HTTPException(status_code=400, detail=f"Registration failed: {str(e)}") from e


@router.get("/{node_id}")
async def get_node(
    node_id: str,
    store: NodeStore = Depends(get_node_store),
) -> NodeMetadata:
    """
    Get metadata for a specific node.

    Path Parameters:
    - node_id: Node identifier

    Returns:
    - NodeMetadata: The node's metadata (404 if not found)
    """
    node = store.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return node


@router.delete("/{node_id}")
async def unregister_node(
    node_id: str,
    store: NodeStore = Depends(get_node_store),
) -> dict:
    """
    Unregister a node from the catalog.

    Path Parameters:
    - node_id: Node identifier to remove

    Returns:
    - status: "ok" if removed, or error
    - message: Status message
    """
    removed = store.unregister_node(node_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return {
        "status": "ok",
        "message": f"Node unregistered: {node_id}",
    }


@router.get("/domains/list")
async def get_domains(
    store: NodeStore = Depends(get_node_store),
) -> DomainsResponse:
    """
    Get list of all registered domains.

    Returns:
    - domains: Array of domain names
    - total: Total number of domains
    """
    try:
        domains = store.get_domain_list()
        return DomainsResponse(domains=domains, total=len(domains))
    except Exception as e:
        logger.error(f"Error fetching domain list: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch domains") from e


# ---------------------------------------------------------------------------
# Graph Execution
# ---------------------------------------------------------------------------


class GraphNodeRequest(BaseModel):
    """A node definition within a graph execution request."""

    id: str = Field(..., description="Unique node identifier within the graph")
    node_type: str = Field(..., description="Node type (e.g. 'audio.transcribe')")
    label: str = Field(default="", description="Human-readable label")
    config: dict = Field(default_factory=dict, description="Node configuration")
    domain: str | None = Field(None, description="Domain override")


class GraphEdgeRequest(BaseModel):
    """A directed edge connecting two nodes in a graph."""

    id: str = Field(..., description="Unique edge identifier")
    source_node: str = Field(..., description="Source node ID")
    source_port: str = Field(..., description="Source output port name")
    target_node: str = Field(..., description="Target node ID")
    target_port: str = Field(..., description="Target input port name")


class GraphExecuteRequest(BaseModel):
    """Request body for graph execution."""

    graph_id: str = Field(default="", description="Graph identifier")
    name: str = Field(default="", description="Graph name")
    nodes: list[GraphNodeRequest] = Field(default_factory=list, description="Graph nodes")
    edges: list[GraphEdgeRequest] = Field(default_factory=list, description="Graph edges")
    mode: str = Field(default="eager", description="Execution mode: 'eager' or 'lazy'")
    target_nodes: list[str] = Field(
        default_factory=list,
        description="Target node IDs for lazy mode (empty = all sink nodes)",
    )
    timeout_seconds: float | None = Field(
        None, description="Execution timeout in seconds (None = no timeout)"
    )


@router.post("/graphs/execute")
async def execute_graph(req: GraphExecuteRequest) -> dict:
    """
    Execute a DAG graph via the node engine.

    Request Body:
    - graph_id: Optional graph identifier
    - nodes: List of GraphNodeRequest (id, node_type, config, ...)
    - edges: List of GraphEdgeRequest (source/target node + port)
    - mode: 'eager' (default) or 'lazy'
    - target_nodes: For lazy mode, the nodes to compute (default: all sinks)
    - timeout_seconds: Optional execution timeout

    Returns:
    - graph_id, status, outputs, error, node_records, total_time_ms
    """
    from mascarade.node_engine.engine import CycleDetectedError
    from mascarade.node_engine.executor import GraphExecutor
    from mascarade.node_engine.graph import Graph, GraphEdge, GraphNode
    from mascarade.node_engine.runtime import ExecutionMode

    # Validate execution mode
    try:
        mode = ExecutionMode(req.mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode {req.mode!r}. Allowed: 'eager', 'lazy'.",
        ) from None

    # Validate request structure before graph construction/execution
    if not req.nodes:
        raise HTTPException(status_code=400, detail="Graph must contain at least one node.")

    node_ids = [n.id for n in req.nodes]
    node_id_set = set(node_ids)
    if len(node_id_set) != len(node_ids):
        raise HTTPException(status_code=400, detail="Graph contains duplicate node IDs.")

    invalid_edges = [
        e.id
        for e in req.edges
        if e.source_node not in node_id_set or e.target_node not in node_id_set
    ]
    if invalid_edges:
        raise HTTPException(
            status_code=400,
            detail=f"Graph edges reference unknown nodes: {', '.join(invalid_edges)}",
        )

    if req.target_nodes:
        unknown_targets = sorted(set(req.target_nodes) - node_id_set)
        if unknown_targets:
            raise HTTPException(
                status_code=400,
                detail=f"target_nodes contain unknown IDs: {', '.join(unknown_targets)}",
            )

    # Build dataclass graph from request
    try:
        nodes = [
            GraphNode(
                id=n.id,
                node_type=n.node_type,
                label=n.label,
                config=n.config,
                domain=n.domain,
            )
            for n in req.nodes
        ]
        edges = [
            GraphEdge(
                id=e.id,
                source_node=e.source_node,
                source_port=e.source_port,
                target_node=e.target_node,
                target_port=e.target_port,
            )
            for e in req.edges
        ]
        graph = Graph(id=req.graph_id, name=req.name, nodes=nodes, edges=edges)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid graph structure: {e}") from e

    # Execute
    try:
        executor = GraphExecutor()
        target_set = set(req.target_nodes) if req.target_nodes else None
        result = await executor.execute_graph(
            graph,
            mode=mode,
            target_nodes=target_set,
            timeout_seconds=req.timeout_seconds,
        )
    except CycleDetectedError as e:
        raise HTTPException(status_code=400, detail=f"Graph cycle detected: {e}") from e
    except Exception as e:
        logger.error(f"Graph execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Graph execution failed: {e}") from e

    return {
        "graph_id": result.graph_id,
        "status": result.status,
        "outputs": result.outputs,
        "error": result.error,
        "node_records": [
            {
                "node_id": r.node_id,
                "status": r.status,
                "outputs": r.outputs,
                "error": r.error,
                "error_type": r.error_type,
                "execution_time_ms": r.execution_time_ms,
            }
            for r in result.node_records
        ],
        "total_time_ms": result.total_time_ms,
    }
