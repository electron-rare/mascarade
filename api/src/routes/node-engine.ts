import { Hono, type Context } from "hono";
import { promises as fs } from "node:fs";
import { join } from "node:path";
import { emitStructuredLog } from "../lib/otel.js";

const nodeEngine = new Hono();
const GRAPHS_DIR = process.env.NODE_ENGINE_GRAPHS_DIR || "./data/node-engine/graphs";
const SAFE_ID_RE = /^[\w-]+$/;

type GraphMetadata = {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  nodes_count?: number;
  edges_count?: number;
};

type GraphData = {
  id: string;
  name: string;
  description?: string;
  nodes: unknown[];
  edges: unknown[];
  metadata: GraphMetadata;
};

async function ensureGraphsDir(): Promise<void> {
  try {
    await fs.mkdir(GRAPHS_DIR, { recursive: true });
  } catch (err: unknown) {
    if (err && typeof err === "object" && "code" in err && err.code !== "EEXIST") {
      throw err;
    }
  }
}

function validateGraphId(id: string): boolean {
  return SAFE_ID_RE.test(id) && id.length > 0 && id.length <= 64;
}

function graphFilePath(id: string): string {
  return join(GRAPHS_DIR, `${id}.json`);
}

async function graphExists(id: string): Promise<boolean> {
  try {
    await fs.access(graphFilePath(id));
    return true;
  } catch {
    return false;
  }
}

async function readGraph(id: string): Promise<GraphData | null> {
  try {
    const content = await fs.readFile(graphFilePath(id), "utf-8");
    return JSON.parse(content) as GraphData;
  } catch {
    return null;
  }
}

async function writeGraph(id: string, data: GraphData): Promise<void> {
  await ensureGraphsDir();
  await fs.writeFile(graphFilePath(id), JSON.stringify(data, null, 2), "utf-8");
}

async function deleteGraph(id: string): Promise<boolean> {
  try {
    await fs.unlink(graphFilePath(id));
    return true;
  } catch {
    return false;
  }
}

async function listGraphs(): Promise<GraphMetadata[]> {
  await ensureGraphsDir();
  try {
    const files = await fs.readdir(GRAPHS_DIR);
    const graphs: GraphMetadata[] = [];

    for (const file of files) {
      if (!file.endsWith(".json")) {
        continue;
      }

      const id = file.replace(".json", "");
      const graph = await readGraph(id);
      if (graph && graph.metadata) {
        graphs.push(graph.metadata);
      }
    }

    return graphs.sort((a, b) =>
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
  } catch {
    return [];
  }
}

function generateGraphId(name: string): string {
  const timestamp = Date.now();
  const safeName = name
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-+/g, "-")
    .substring(0, 32);
  return `${safeName}-${timestamp}`;
}

// GET /graphs - List all saved graphs
nodeEngine.get("/graphs", async (c: Context) => {
  try {
    const graphs = await listGraphs();

    emitStructuredLog({
      service: "api",
      severity: "info",
      message: "Listed node engine graphs",
      graph_count: graphs.length,
    });

    return c.json({ graphs, total: graphs.length });
  } catch (err: unknown) {
    emitStructuredLog({
      service: "api",
      severity: "error",
      message: "Failed to list graphs",
      error: err instanceof Error ? err.message : String(err),
    });
    return c.json({ error: "Failed to list graphs" }, 500);
  }
});

// GET /graphs/:id - Get a specific graph
nodeEngine.get("/graphs/:id", async (c: Context) => {
  const id = c.req.param("id") ?? "";

  if (!validateGraphId(id)) {
    return c.json({ error: "Invalid graph ID" }, 400);
  }

  try {
    const graph = await readGraph(id);

    if (!graph) {
      return c.json({ error: "Graph not found" }, 404);
    }

    emitStructuredLog({
      service: "api",
      severity: "info",
      message: "Retrieved node engine graph",
      graph_id: id,
      graph_name: graph.name,
    });

    return c.json(graph);
  } catch (err: unknown) {
    emitStructuredLog({
      service: "api",
      severity: "error",
      message: "Failed to retrieve graph",
      graph_id: id,
      error: err instanceof Error ? err.message : String(err),
    });
    return c.json({ error: "Failed to retrieve graph" }, 500);
  }
});

// POST /graphs - Create a new graph
nodeEngine.post("/graphs", async (c: Context) => {
  let body: Record<string, unknown>;

  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "Invalid JSON body" }, 400);
  }

  const name = typeof body.name === "string" ? body.name.trim() : "";
  const description = typeof body.description === "string" ? body.description.trim() : undefined;
  const nodes = Array.isArray(body.nodes) ? body.nodes : [];
  const edges = Array.isArray(body.edges) ? body.edges : [];
  const customId = typeof body.id === "string" ? body.id.trim() : undefined;

  if (!name) {
    return c.json({ error: "Graph name is required" }, 400);
  }

  const id = customId && validateGraphId(customId) ? customId : generateGraphId(name);

  if (!validateGraphId(id)) {
    return c.json({ error: "Invalid graph ID" }, 400);
  }

  if (await graphExists(id)) {
    return c.json({ error: "Graph ID already exists" }, 409);
  }

  const now = new Date().toISOString();
  const metadata: GraphMetadata = {
    id,
    name,
    description,
    created_at: now,
    updated_at: now,
    nodes_count: nodes.length,
    edges_count: edges.length,
  };

  const graph: GraphData = {
    id,
    name,
    description,
    nodes,
    edges,
    metadata,
  };

  try {
    await writeGraph(id, graph);

    emitStructuredLog({
      service: "api",
      severity: "info",
      message: "Created node engine graph",
      graph_id: id,
      graph_name: name,
      nodes_count: nodes.length,
      edges_count: edges.length,
    });

    return c.json(graph, 201);
  } catch (err: unknown) {
    emitStructuredLog({
      service: "api",
      severity: "error",
      message: "Failed to create graph",
      graph_id: id,
      error: err instanceof Error ? err.message : String(err),
    });
    return c.json({ error: "Failed to create graph" }, 500);
  }
});

// PUT /graphs/:id - Update an existing graph
nodeEngine.put("/graphs/:id", async (c: Context) => {
  const id = c.req.param("id") ?? "";

  if (!validateGraphId(id)) {
    return c.json({ error: "Invalid graph ID" }, 400);
  }

  const existingGraph = await readGraph(id);
  if (!existingGraph) {
    return c.json({ error: "Graph not found" }, 404);
  }

  let body: Record<string, unknown>;

  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "Invalid JSON body" }, 400);
  }

  const name = typeof body.name === "string" ? body.name.trim() : existingGraph.name;
  const description = typeof body.description === "string" ? body.description.trim() : existingGraph.description;
  const nodes = Array.isArray(body.nodes) ? body.nodes : existingGraph.nodes;
  const edges = Array.isArray(body.edges) ? body.edges : existingGraph.edges;

  if (!name) {
    return c.json({ error: "Graph name is required" }, 400);
  }

  const now = new Date().toISOString();
  const metadata: GraphMetadata = {
    id,
    name,
    description,
    created_at: existingGraph.metadata.created_at,
    updated_at: now,
    nodes_count: nodes.length,
    edges_count: edges.length,
  };

  const graph: GraphData = {
    id,
    name,
    description,
    nodes,
    edges,
    metadata,
  };

  try {
    await writeGraph(id, graph);

    emitStructuredLog({
      service: "api",
      severity: "info",
      message: "Updated node engine graph",
      graph_id: id,
      graph_name: name,
      nodes_count: nodes.length,
      edges_count: edges.length,
    });

    return c.json(graph);
  } catch (err: unknown) {
    emitStructuredLog({
      service: "api",
      severity: "error",
      message: "Failed to update graph",
      graph_id: id,
      error: err instanceof Error ? err.message : String(err),
    });
    return c.json({ error: "Failed to update graph" }, 500);
  }
});

// DELETE /graphs/:id - Delete a graph
nodeEngine.delete("/graphs/:id", async (c: Context) => {
  const id = c.req.param("id") ?? "";

  if (!validateGraphId(id)) {
    return c.json({ error: "Invalid graph ID" }, 400);
  }

  const graph = await readGraph(id);
  if (!graph) {
    return c.json({ error: "Graph not found" }, 404);
  }

  try {
    const deleted = await deleteGraph(id);

    if (!deleted) {
      return c.json({ error: "Failed to delete graph" }, 500);
    }

    emitStructuredLog({
      service: "api",
      severity: "info",
      message: "Deleted node engine graph",
      graph_id: id,
      graph_name: graph.name,
    });

    return c.json({ success: true, message: "Graph deleted" });
  } catch (err: unknown) {
    emitStructuredLog({
      service: "api",
      severity: "error",
      message: "Failed to delete graph",
      graph_id: id,
      error: err instanceof Error ? err.message : String(err),
    });
    return c.json({ error: "Failed to delete graph" }, 500);
  }
});

export { nodeEngine };
