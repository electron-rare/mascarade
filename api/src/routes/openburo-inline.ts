import { Hono } from "hono";
import { APP_REGISTRY } from "./openburo.js";
import { BUSINESS_OBJECT_SCHEMAS } from "./openburo-objects.js";
import { connectors } from "./openburo-connectors.js";
import { workspaces } from "./openburo-workspaces.js";
import { search } from "./openburo-search.js";

const openburoInline = new Hono();

// Apps
openburoInline.get("/apps", (c) => {
  const capability = c.req.query("capability");
  const node = c.req.query("node");
  let apps = APP_REGISTRY;
  if (capability) apps = apps.filter((a: any) => a.capabilities.includes(capability));
  if (node) apps = apps.filter((a: any) => a.node === node);
  return c.json({ apps, count: apps.length });
});

openburoInline.get("/apps/:id", (c) => {
  const entry = APP_REGISTRY.find((a: any) => a.id === c.req.param("id"));
  if (!entry) return c.json({ error: "App not found" }, 404);
  return c.json(entry);
});

openburoInline.get("/capabilities", (c) => {
  const caps = [...new Set(APP_REGISTRY.flatMap((a: any) => a.capabilities))].sort();
  return c.json({ capabilities: caps });
});

openburoInline.get("/health", async (c) => {
  const results = await Promise.allSettled(
    APP_REGISTRY.filter((a: any) => a.health).map(async (a: any) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      try {
        const res = await fetch(a.health, { signal: controller.signal });
        return { id: a.id, name: a.name, status: res.ok ? "up" : "down", code: res.status };
      } catch { return { id: a.id, name: a.name, status: "down", code: 0 }; }
      finally { clearTimeout(timeout); }
    })
  );
  const statuses = results.map((r: any) => r.status === "fulfilled" ? r.value : { id: "?", name: "?", status: "error", code: 0 });
  return c.json({ total: statuses.length, up: statuses.filter((s: any) => s.status === "up").length, down: statuses.length - statuses.filter((s: any) => s.status === "up").length, services: statuses });
});

// Business Objects schemas
openburoInline.get("/objects/schemas", (c) => {
  const types = Object.keys(BUSINESS_OBJECT_SCHEMAS).map((k) => ({
    type: k,
    description: (BUSINESS_OBJECT_SCHEMAS as any)[k].description,
    required: (BUSINESS_OBJECT_SCHEMAS as any)[k].required,
    property_count: Object.keys((BUSINESS_OBJECT_SCHEMAS as any)[k].properties).length,
  }));
  return c.json({ schemas: types, count: types.length });
});

openburoInline.get("/objects/schemas/:type", (c) => {
  const schema = (BUSINESS_OBJECT_SCHEMAS as any)[c.req.param("type")];
  if (!schema) return c.json({ error: "Unknown type" }, 404);
  return c.json(schema);
});

// Workspaces (cross-app project aggregation)
openburoInline.get("/workspaces", (c) => workspaces.fetch(new Request("http://x/"), c.env));
openburoInline.post("/workspaces", async (c) => workspaces.fetch(new Request("http://x/", { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body }), c.env));
openburoInline.get("/workspaces/:id", (c) => workspaces.fetch(new Request("http://x/" + c.req.param("id")), c.env));
openburoInline.put("/workspaces/:id", async (c) => workspaces.fetch(new Request("http://x/" + c.req.param("id"), { method: "PUT", headers: c.req.raw.headers, body: c.req.raw.body }), c.env));
openburoInline.post("/workspaces/:id/resources", async (c) => workspaces.fetch(new Request("http://x/" + c.req.param("id") + "/resources", { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body }), c.env));

// Unified Search (Qdrant + event bus fallback)
openburoInline.get("/search", (c) => {
  const url = new URL("http://x/");
  for (const [k, v] of Object.entries(c.req.query())) url.searchParams.set(k, v as string);
  return search.fetch(new Request(url));
});
openburoInline.post("/search/index", async (c) => search.fetch(new Request("http://x/index", { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body })));
openburoInline.get("/search/stats", (c) => search.fetch(new Request("http://x/stats")));

// Connectors (Dolibarr, Grist, N8N webhooks)
openburoInline.post("/connectors/grist/webhook", async (c) => {
  const req = new Request("http://x/grist/webhook" + (c.req.query("doc") ? "?doc=" + c.req.query("doc") : ""), { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body });
  return connectors.fetch(req);
});
openburoInline.post("/connectors/dolibarr/webhook", async (c) => {
  return connectors.fetch(new Request("http://x/dolibarr/webhook", { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body }));
});
openburoInline.post("/connectors/n8n/webhook", async (c) => {
  return connectors.fetch(new Request("http://x/n8n/webhook", { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body }));
});
openburoInline.get("/connectors/status", async (c) => {
  return connectors.fetch(new Request("http://x/status"));
});

// Notifications -> ntfy
openburoInline.post("/notifications", async (c) => {
  const body = await c.req.json();
  if (!body.title) return c.json({ error: "Missing: title" }, 400);

  const ntfyUrl = process.env.NTFY_URL || "http://localhost:2586";
  const topic = body.topic || "openburo";

  try {
    await fetch(ntfyUrl + "/" + topic, {
      method: "POST",
      headers: {
        "Title": body.title,
        "Priority": body.priority || "default",
        "Tags": body.tags || "openburo",
        ...(process.env.NTFY_TOKEN ? { "Authorization": `Bearer ${process.env.NTFY_TOKEN}` } : {}),
        ...(body.click ? { "Click": body.click } : {}),
      },
      body: body.message || body.title,
    });
    return c.json({ sent: true, topic });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

export { openburoInline };
