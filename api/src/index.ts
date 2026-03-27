import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { Hono } from "hono";
import { logger } from "hono/logger";
import { existsSync } from "node:fs";
import { authMiddleware } from "./middleware/auth.js";
import { corsMiddleware } from "./middleware/cors.js";
import { rateLimitMiddleware } from "./middleware/rate-limit.js";
import { securityHeaders } from "./middleware/security.js";
import { auth } from "./routes/auth.js";
import { health } from "./routes/health.js";
import { version } from "./routes/version.js";
import { agents } from "./routes/agents.js";
import { cluster } from "./routes/cluster.js";
import { knowledgeBase } from "./routes/knowledgeBase.js";
import { qdrantKnowledge } from "./routes/qdrantKnowledge.js";
import { cad } from "./routes/cad.js";
import { comfyui } from "./routes/comfyui.js";
import { ops } from "./routes/ops.js";
import { industrial } from "./routes/industrial.js";
import { industrialMcp } from "./routes/mcpIndustrial.js";
import { killlife } from "./routes/killlife.js";
import { settings } from "./routes/settings.js";
import { chat } from "./routes/chat.js";
import { pipeline } from "./routes/pipeline.js";
import { analytics } from "./routes/analytics.js";
import { users } from "./routes/users.js";
import { p2p } from "./routes/p2p.js";
import { finetune } from "./routes/finetune.js";
import { llmProviders } from "./routes/llmProviders.js";
import { providers } from "./routes/providers.js";
import { cliAgents } from "./routes/cliAgents.js";
import { models } from "./routes/models.js";
import { nodeEngine } from "./routes/node-engine.js";
import { ollama } from "./routes/ollama.js";
import { bodyLimit } from "hono/body-limit";

const app = new Hono();
const hasFrontend = existsSync("./public/index.html");

const MAX_BODY_SIZE = parseInt(process.env.MAX_BODY_SIZE || "1048576", 10); // 1 MB default

app.use("*", corsMiddleware);
app.use("*", securityHeaders);
app.use("*", bodyLimit({ maxSize: MAX_BODY_SIZE }));
app.use("*", logger());
app.onError((err, c) => {
  console.error("Internal error:", err);
  return c.json({ error: "Internal server error" }, 500);
});

app.route("/health", health);
app.route("/v1/version", version);
// Auth first — reject unauthenticated before consuming rate-limit quota
app.use("/v1/api/*", authMiddleware);
app.use("/v1/api/*", rateLimitMiddleware);
app.route("/v1/api/agents", agents);
app.route("/v1/api/cluster", cluster);
app.route("/v1/api/knowledge-base", knowledgeBase);
app.route("/v1/api/qdrant-knowledge", qdrantKnowledge);
app.route("/v1/api/cad", cad);
app.route("/v1/api/comfyui", comfyui);
app.route("/v1/api/ops", ops);
app.route("/v1/api/industrial", industrial);
app.route("/v1/api/mcp/industrial", industrialMcp);
app.route("/v1/api/killlife", killlife);
app.route("/v1/api/settings", settings);
app.route("/v1/api/providers", providers);
app.route("/v1/api/cli-agents", cliAgents);
app.route("/v1/api/models", models);
app.route("/v1/api/node-engine", nodeEngine);
app.use("/api/auth/*", rateLimitMiddleware);
app.route("/api/auth", auth);
// Auth first — reject unauthenticated before consuming rate-limit quota
app.use("/api/*", authMiddleware);
app.use("/api/*", rateLimitMiddleware);
app.route("/api/agents", agents);
app.route("/api/cluster", cluster);
app.route("/api/knowledge-base", knowledgeBase);
app.route("/api/qdrant-knowledge", qdrantKnowledge);
app.route("/api/cad", cad);
app.route("/api/comfyui", comfyui);
app.route("/api/ops", ops);
app.route("/api/industrial", industrial);
app.route("/api/mcp/industrial", industrialMcp);
app.route("/api/killlife", killlife);
app.route("/api/settings", settings);
app.route("/api/providers", providers);
app.route("/api/cli-agents", cliAgents);
app.route("/api/v1/chat", chat);
app.route("/api/v1/models", models);
app.route("/api/node-engine", nodeEngine);
app.route("/api/pipeline", pipeline);
app.route("/api/analytics", analytics);
app.route("/api/users", users);
app.route("/api/p2p", p2p);
app.route("/api/finetune", finetune);
app.route("/api/v2/llm-providers", llmProviders);
app.route("/api", ollama);

// Open Buro API (direct handlers to avoid sub-app priority issues)
import { APP_REGISTRY } from "./routes/openburo.js";
import { openburoEvents } from "./routes/openburo-events.js";
import { BUSINESS_OBJECT_SCHEMAS } from "./routes/openburo-objects.js";


app.get("/openburo/apps", (c) => { 
  const capability = c.req.query("capability");
  const node = c.req.query("node");
  let apps = APP_REGISTRY;
  if (capability) apps = apps.filter((a: any) => a.capabilities.includes(capability));
  if (node) apps = apps.filter((a: any) => a.node === node);
  return c.json({ apps, count: apps.length });
});

app.get("/openburo/apps/:id", (c) => {
  const entry = APP_REGISTRY.find((a: any) => a.id === c.req.param("id"));
  if (!entry) return c.json({ error: "App not found" }, 404);
  return c.json(entry);
});

app.get("/openburo/capabilities", (c) => {
  const caps = [...new Set(APP_REGISTRY.flatMap((a: any) => a.capabilities))].sort();
  return c.json({ capabilities: caps });
});

app.get("/openburo/health", async (c) => {
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

// Open Buro: Event bus (CloudEvents + Redis Streams)

// Open Buro: Business Objects (direct handlers)
app.get("/openburo/objects/schemas", (c) => {
  const types = Object.keys(BUSINESS_OBJECT_SCHEMAS).map((k) => ({
    type: k,
    description: (BUSINESS_OBJECT_SCHEMAS as any)[k].description,
    required: (BUSINESS_OBJECT_SCHEMAS as any)[k].required,
    property_count: Object.keys((BUSINESS_OBJECT_SCHEMAS as any)[k].properties).length,
  }));
  return c.json({ schemas: types, count: types.length });
});

app.get("/openburo/objects/schemas/:type", (c) => {
  const schema = (BUSINESS_OBJECT_SCHEMAS as any)[c.req.param("type")];
  if (!schema) return c.json({ error: "Unknown type" }, 404);
  return c.json(schema);
});

// Phase 2: objects/:type routes handled by openburo-objects sub-app
import { openburoObjects } from "./routes/openburo-objects.js";
app.route("/openburo/objects", openburoObjects);


// Open Buro Phase 2: Event Bus (CloudEvents + Redis Streams)

const STREAM_KEY = "openburo:events";
let _redis: any = null;

async function getEventRedis() {
  if (!_redis) {
    const { createClient } = await import("redis") as any;
    _redis = createClient({ url: process.env.REDIS_URL || "redis://:RedisTower2026!@mascarade-redis:6379/15" });
    _redis.on("error", (err: Error) => console.error("[openburo/events] Redis:", err.message));
    await _redis.connect();
  }
  return _redis;
}

app.post("/openburo/events", async (c) => {
  const body = await c.req.json();
  if (!body.type || !body.source) return c.json({ error: "Missing: type, source" }, 400);
  const event = {
    specversion: "1.0",
    id: body.id || crypto.randomUUID(),
    type: body.type,
    source: body.source,
    time: body.time || new Date().toISOString(),
    subject: body.subject,
    datacontenttype: "application/json",
    data: body.data || {},
  };
  try {
    const r = await getEventRedis();
    await r.xAdd(STREAM_KEY, "*", { event: JSON.stringify(event) });
    return c.json({ status: "published", id: event.id, type: event.type });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

app.get("/openburo/events", async (c) => {
  const limit = parseInt(c.req.query("limit") || "50");
  const type = c.req.query("type");
  try {
    const r = await getEventRedis();
    const entries = await r.xRevRange(STREAM_KEY, "+", "-", { COUNT: limit });
    let events = entries.map((e: any) => ({ stream_id: e.id, ...JSON.parse(e.message.event) }));
    if (type) events = events.filter((e: any) => e.type === type || e.type.startsWith(type + "."));
    return c.json({ events, count: events.length });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

app.get("/openburo/events/stats", async (c) => {
  try {
    const r = await getEventRedis();
    const len = await r.xLen(STREAM_KEY);
    return c.json({ total: len, stream: STREAM_KEY });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

if (hasFrontend) {
  app.use("/assets/*", serveStatic({ root: "./public" }));
  app.use("/favicon.ico", serveStatic({ root: "./public" }));
  // SPA: notFound handler serves index.html for frontend routes only
  app.notFound((c) => {
    if (c.req.path.startsWith("/openburo") || c.req.path.startsWith("/api") || c.req.path.startsWith("/v1")) {
      return c.json({ error: "Not found" }, 404);
    }
    const fs = require("node:fs");
    return c.html(fs.readFileSync("./public/index.html", "utf-8"));
  });
} else {
  app.get("/", (c) => c.json({ name: "mascarade-api", version: "0.1.0" }));
}

app.notFound((c) => c.json({ error: "Not found" }, 404));

const port = parseInt(process.env.API_PORT || "3100", 10);

console.log(`Mascarade API listening on port ${port}`);
serve({ fetch: app.fetch, port });

export { app };
