import { Hono } from "hono";
import { emitStructuredLog } from "../lib/otel.js";
import type { Graph, GraphNode, GraphEdge, GraphStatus } from "../types/node-engine.js";

const nodes = new Hono();
const graphs = new Hono();

type NodePort = {
  id: string;
  label: string;
  type: string | Record<string, unknown>;
  required: boolean;
  default?: unknown;
  description?: string;
};

type NodeTypeResponse = {
  id: string;
  domain: string;
  label: string;
  description: string;
  version: string;
  inputs: NodePort[];
  outputs: NodePort[];
  config_schema: Record<string, unknown>;
  tags: string[];
  deprecated: boolean;
  deprecated_by: string | null;
};

type NodeCatalogResponse = {
  node_types: NodeTypeResponse[];
  domains: string[];
  total_count: number;
};

/**
 * GET /catalog
 * Returns the catalog of available node types for the node engine.
 *
 * Phase 0 implementation: Returns empty catalog structure.
 * Will be enhanced in later phases to proxy to core NodeTypeRegistry.
 */
nodes.get("/catalog", async (c) => {
  emitStructuredLog({
    severity: "info",
    service: "api",
    message: "Fetching node catalog",
    source: "nodes.catalog",
  });

  // Phase 0: Return empty catalog structure
  // TODO: In Phase 1+, proxy to core /nodes/catalog endpoint
  const emptyResponse: NodeCatalogResponse = {
    node_types: [],
    domains: [],
    total_count: 0,
  };

  return c.json(emptyResponse);
});

/**
 * GET /catalog/:domain
 * Returns node types filtered by domain.
 *
 * Phase 0 implementation: Returns empty catalog structure.
 * Will be enhanced in later phases to proxy to core NodeTypeRegistry.
 */
nodes.get("/catalog/:domain", async (c) => {
  const domain = c.req.param("domain");

  emitStructuredLog({
    severity: "info",
    service: "api",
    message: `Fetching node catalog for domain: ${domain}`,
    source: "nodes.catalog",
  });

  // Phase 0: Return empty catalog structure
  // TODO: In Phase 1+, proxy to core /nodes/catalog?domain=X endpoint
  const emptyResponse: NodeCatalogResponse = {
    node_types: [],
    domains: [],
    total_count: 0,
  };

  return c.json(emptyResponse);
});

/**
 * Graph CRUD Endpoints
 * Phase 0 implementation: In-memory storage for graphs.
 * Will be enhanced in later phases to use core persistence layer.
 */

// In-memory graph storage for Phase 0
// TODO: In Phase 1+, replace with core persistence layer
const graphStore = new Map<string, Graph>();
let graphIdCounter = 1;

type CreateGraphRequest = {
  name: string;
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  metadata?: Record<string, unknown>;
};

type UpdateGraphRequest = {
  name?: string;
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  status?: GraphStatus;
  metadata?: Record<string, unknown>;
};

/**
 * POST /
 * Create a new graph.
 *
 * Phase 0 implementation: Store in memory.
 * Will be enhanced in later phases to persist via core GraphSerializer.
 */
graphs.post("/", async (c) => {
  try {
    const body = await c.req.json<CreateGraphRequest>();

    if (!body.name || typeof body.name !== "string" || !body.name.trim()) {
      emitStructuredLog({
        severity: "warning",
        service: "api",
        message: "Invalid graph creation request: name is required",
        source: "graphs.create",
      });
      return c.json({ error: "Graph name is required" }, 400);
    }

    const graphId = `graph-${graphIdCounter++}`;
    const now = new Date().toISOString();

    const graph: Graph = {
      id: graphId,
      name: body.name.trim(),
      version: 1,
      status: "draft",
      nodes: body.nodes || [],
      edges: body.edges || [],
      metadata: {
        ...(body.metadata || {}),
        created_at: now,
        updated_at: now,
      },
    };

    graphStore.set(graphId, graph);

    emitStructuredLog({
      severity: "info",
      service: "api",
      message: `Created graph: ${graphId}`,
      source: "graphs.create",
    });

    return c.json(graph, 201);
  } catch (error) {
    emitStructuredLog({
      severity: "error",
      service: "api",
      message: `Failed to create graph: ${error}`,
      source: "graphs.create",
    });
    return c.json({ error: "Failed to create graph" }, 500);
  }
});

/**
 * GET /
 * List all graphs.
 *
 * Phase 0 implementation: Return from in-memory storage.
 * Will be enhanced in later phases to query core persistence layer.
 */
graphs.get("/", async (c) => {
  emitStructuredLog({
    severity: "info",
    service: "api",
    message: "Listing all graphs",
    source: "graphs.list",
  });

  const allGraphs = Array.from(graphStore.values());

  return c.json({
    graphs: allGraphs,
    total_count: allGraphs.length,
  });
});

/**
 * GET /:id
 * Get a specific graph by ID.
 *
 * Phase 0 implementation: Return from in-memory storage.
 * Will be enhanced in later phases to query core persistence layer.
 */
graphs.get("/:id", async (c) => {
  const graphId = c.req.param("id");

  emitStructuredLog({
    severity: "info",
    service: "api",
    message: `Fetching graph: ${graphId}`,
    source: "graphs.get",
  });

  const graph = graphStore.get(graphId);

  if (!graph) {
    emitStructuredLog({
      severity: "warning",
      service: "api",
      message: `Graph not found: ${graphId}`,
      source: "graphs.get",
    });
    return c.json({ error: "Graph not found" }, 404);
  }

  return c.json(graph);
});

/**
 * PUT /:id
 * Update an existing graph.
 *
 * Phase 0 implementation: Update in-memory storage.
 * Will be enhanced in later phases to persist via core GraphSerializer.
 */
graphs.put("/:id", async (c) => {
  const graphId = c.req.param("id");

  try {
    const body = await c.req.json<UpdateGraphRequest>();

    const existingGraph = graphStore.get(graphId);

    if (!existingGraph) {
      emitStructuredLog({
        severity: "warning",
        service: "api",
        message: `Graph not found for update: ${graphId}`,
        source: "graphs.update",
      });
      return c.json({ error: "Graph not found" }, 404);
    }

    const updatedGraph: Graph = {
      ...existingGraph,
      ...(body.name && { name: body.name }),
      ...(body.nodes && { nodes: body.nodes }),
      ...(body.edges && { edges: body.edges }),
      ...(body.status && { status: body.status }),
      version: existingGraph.version + 1,
      metadata: {
        ...existingGraph.metadata,
        ...(body.metadata || {}),
        updated_at: new Date().toISOString(),
      },
    };

    graphStore.set(graphId, updatedGraph);

    emitStructuredLog({
      severity: "info",
      service: "api",
      message: `Updated graph: ${graphId}`,
      source: "graphs.update",
    });

    return c.json(updatedGraph);
  } catch (error) {
    emitStructuredLog({
      severity: "error",
      service: "api",
      message: `Failed to update graph ${graphId}: ${error}`,
      source: "graphs.update",
    });
    return c.json({ error: "Failed to update graph" }, 500);
  }
});

/**
 * DELETE /:id
 * Delete a graph.
 *
 * Phase 0 implementation: Remove from in-memory storage.
 * Will be enhanced in later phases to delete via core persistence layer.
 */
graphs.delete("/:id", async (c) => {
  const graphId = c.req.param("id");

  emitStructuredLog({
    severity: "info",
    service: "api",
    message: `Deleting graph: ${graphId}`,
    source: "graphs.delete",
  });

  const existed = graphStore.delete(graphId);

  if (!existed) {
    emitStructuredLog({
      severity: "warning",
      service: "api",
      message: `Graph not found for deletion: ${graphId}`,
      source: "graphs.delete",
    });
    return c.json({ error: "Graph not found" }, 404);
  }

  return c.json({ success: true, message: "Graph deleted" });
});

export { nodes, graphs };
