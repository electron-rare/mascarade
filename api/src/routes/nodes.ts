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

function emptyCatalog(): NodeCatalogResponse {
  return {
    node_types: [],
    domains: [],
    total_count: 0,
  };
}

/**
 * GET /catalog
 * Returns the catalog of available nodes from the core engine.
 *
 * Proxies to core /v1/nodes/catalog endpoint (Phase B implementation).
 */
nodes.get("/catalog", async (c) => {
  const domain = c.req.query("domain");
  
  emitStructuredLog({
    severity: "info",
    service: "api",
    message: `Proxying node catalog request${domain ? ` for domain: ${domain}` : ""}`,
    source: "nodes.catalog",
  });

  try {
    const coreUrl = process.env.CORE_URL || "http://core:8100";
    const apiKey = c.req.header("authorization") || "";
    
    const catalogUrl = domain
      ? `${coreUrl}/v1/nodes/catalog?domain=${encodeURIComponent(domain)}`
      : `${coreUrl}/v1/nodes/catalog`;

    const response = await fetch(catalogUrl, {
      headers: {
        "Authorization": apiKey,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Core returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return c.json(data);
  } catch (error) {
    emitStructuredLog({
      severity: "warning",
      service: "api",
      message: `Falling back to empty node catalog: ${error instanceof Error ? error.message : String(error)}`,
      source: "nodes.catalog",
    });

    return c.json(emptyCatalog());
  }
});

/**
 * GET /catalog/:domain (deprecated)
 * Returns node types filtered by domain.
 * Use GET /catalog?domain=X instead.
 *
 * Kept for backward compatibility.
 */
nodes.get("/catalog/:domain", async (c) => {
  const domain = c.req.param("domain");
  
  // Redirect to query parameter version
  const coreUrl = process.env.CORE_URL || "http://core:8100";
  const apiKey = c.req.header("authorization") || "";

  emitStructuredLog({
    severity: "info",
    service: "api",
    message: `Proxying node catalog request for domain: ${domain}`,
    source: "nodes.catalog.domain",
  });

  try {
    const catalogUrl = `${coreUrl}/v1/nodes/catalog?domain=${encodeURIComponent(domain)}`;
    
    const response = await fetch(catalogUrl, {
      headers: {
        "Authorization": apiKey,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Core returned ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return c.json(data);
  } catch (error) {
    emitStructuredLog({
      severity: "warning",
      service: "api",
      message: `Falling back to empty node catalog for domain ${domain}: ${error instanceof Error ? error.message : String(error)}`,
      source: "nodes.catalog.domain",
    });

    return c.json(emptyCatalog());
  }
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
