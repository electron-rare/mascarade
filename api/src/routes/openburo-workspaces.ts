/**
 * Open Buro — Workspaces (Phase 2)
 * Cross-app project aggregation: docs + contacts + invoices + calendar in one view
 * Storage: PostgreSQL mascarade (table openburo_workspaces)
 */

import { Hono } from "hono";

const workspaces = new Hono();

// In-memory store (Phase 2 MVP — migrate to PostgreSQL in Phase 3)
interface WorkspaceResource {
  app: string;        // e.g. "dolibarr", "grist", "docs"
  type: string;       // e.g. "contact", "document", "invoice"
  id: string;         // ID in source app
  label: string;      // Human-readable label
  url?: string;       // Direct link
}

interface Workspace {
  id: string;
  name: string;
  description?: string;
  owner: string;
  resources: WorkspaceResource[];
  created_at: string;
  updated_at: string;
}

const WORKSPACES: Map<string, Workspace> = new Map();

// POST /openburo/workspaces — create a workspace
workspaces.post("/", async (c) => {
  const body = await c.req.json();
  if (!body.name) return c.json({ error: "Missing: name" }, 400);

  const ws: Workspace = {
    id: crypto.randomUUID(),
    name: body.name,
    description: body.description || "",
    owner: body.owner || "clems",
    resources: body.resources || [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  WORKSPACES.set(ws.id, ws);

  // Publish event
  try {
    await fetch("http://localhost:3000/openburo/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: "workspace.created",
        source: "/openburo/workspaces",
        subject: ws.id,
        data: { name: ws.name, resource_count: ws.resources.length },
      }),
    });
  } catch {}

  return c.json(ws, 201);
});

// GET /openburo/workspaces — list all workspaces
workspaces.get("/", (c) => {
  const list = Array.from(WORKSPACES.values()).sort(
    (a, b) => b.updated_at.localeCompare(a.updated_at)
  );
  return c.json({ workspaces: list, count: list.length });
});

// GET /openburo/workspaces/:id — get workspace details
workspaces.get("/:id", (c) => {
  const ws = WORKSPACES.get(c.req.param("id"));
  if (!ws) return c.json({ error: "Workspace not found" }, 404);
  return c.json(ws);
});

// PUT /openburo/workspaces/:id — update workspace
workspaces.put("/:id", async (c) => {
  const ws = WORKSPACES.get(c.req.param("id"));
  if (!ws) return c.json({ error: "Workspace not found" }, 404);

  const body = await c.req.json();
  if (body.name) ws.name = body.name;
  if (body.description !== undefined) ws.description = body.description;
  if (body.resources) ws.resources = body.resources;
  ws.updated_at = new Date().toISOString();

  return c.json(ws);
});

// POST /openburo/workspaces/:id/resources — add resource to workspace
workspaces.post("/:id/resources", async (c) => {
  const ws = WORKSPACES.get(c.req.param("id"));
  if (!ws) return c.json({ error: "Workspace not found" }, 404);

  const body = await c.req.json();
  if (!body.app || !body.type || !body.id || !body.label) {
    return c.json({ error: "Missing: app, type, id, label" }, 400);
  }

  const resource: WorkspaceResource = {
    app: body.app,
    type: body.type,
    id: body.id,
    label: body.label,
    url: body.url,
  };

  ws.resources.push(resource);
  ws.updated_at = new Date().toISOString();

  // Publish event
  try {
    await fetch("http://localhost:3000/openburo/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: "workspace.resource_added",
        source: "/openburo/workspaces",
        subject: ws.id,
        data: { workspace: ws.name, resource },
      }),
    });
  } catch {}

  return c.json({ workspace_id: ws.id, resource, total_resources: ws.resources.length });
});

// DELETE /openburo/workspaces/:id/resources — remove resource
workspaces.delete("/:id/resources", async (c) => {
  const ws = WORKSPACES.get(c.req.param("id"));
  if (!ws) return c.json({ error: "Workspace not found" }, 404);

  const body = await c.req.json();
  const before = ws.resources.length;
  ws.resources = ws.resources.filter(
    (r) => !(r.app === body.app && r.type === body.type && r.id === body.id)
  );
  ws.updated_at = new Date().toISOString();

  return c.json({ removed: before - ws.resources.length, total_resources: ws.resources.length });
});

// DELETE /openburo/workspaces/:id — delete workspace
workspaces.delete("/:id", (c) => {
  const deleted = WORKSPACES.delete(c.req.param("id"));
  if (!deleted) return c.json({ error: "Workspace not found" }, 404);
  return c.json({ deleted: true });
});

export { workspaces };
