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
import { orchestrateTemplates } from "./routes/orchestrateTemplates.js";
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
app.route("/v1/api/orchestrate/templates", orchestrateTemplates);
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
app.route("/api/orchestrate/templates", orchestrateTemplates);
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

// =============================================================================
// AI endpoints: RAG + Agents + Web Search + Multi-machine Ollama
// =============================================================================
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Multi-machine Ollama routing
const OLLAMA_NODES: Record<string, string> = {
  tower: process.env.OLLAMA_TOWER || "http://mascarade-ollama:11434",
  kxkm: process.env.OLLAMA_KXKM || "http://mascarade-ollama:11434",
};
const OLLAMA_DEFAULT = process.env.OLLAMA_URL || OLLAMA_NODES.tower;
const MODEL_ROUTES: Record<string, string> = {
  "albert": OLLAMA_NODES.kxkm, "mistral:7b": OLLAMA_NODES.kxkm,
  "devstral": OLLAMA_NODES.kxkm, "qwen3:8b": OLLAMA_NODES.kxkm,
  "qwen3:4b": OLLAMA_NODES.tower, "bge-m3": OLLAMA_NODES.kxkm,
};
function ollamaFor(model: string): string { return MODEL_ROUTES[model] || OLLAMA_DEFAULT; }

const QDRANT_URL = process.env.QDRANT_URL || "http://mascarade-qdrant:6333";
const SEARXNG_URL = process.env.SEARXNG_URL || "http://mascarade-searxng:8080";
const RAG_COLLECTION = process.env.RAG_COLLECTION || "mascarade-rag";
const EMBED_MODEL = process.env.EMBED_MODEL || "bge-m3";
const TIMEOUT = 90000;

// Load agents
let AGENTS: Array<Record<string, unknown>> = [];
try { AGENTS = JSON.parse(readFileSync(resolve(process.cwd(), "../core/data/agents.json"), "utf-8")); } catch {}
try { if (!AGENTS.length) AGENTS = JSON.parse(readFileSync("/app/core/data/agents.json", "utf-8")); } catch {}

async function webSearch(query: string): Promise<string[]> {
  try {
    const r = await fetch(`${SEARXNG_URL}/search?${new URLSearchParams({ q: query, format: "json", language: "fr" })}`, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) return [];
    const d = await r.json() as { results?: Array<{ title?: string; url?: string; content?: string }> };
    return (d.results || []).slice(0, 3).map(r => `[${r.title}](${r.url}): ${(r.content || "").slice(0, 200)}`).filter(Boolean);
  } catch { return []; }
}

async function ragSearch(query: string): Promise<string[]> {
  try {
    const eR = await fetch(`${ollamaFor("bge-m3")}/api/embed`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: EMBED_MODEL, input: query }), signal: AbortSignal.timeout(TIMEOUT) });
    if (!eR.ok) return [];
    const eD = await eR.json() as { embeddings?: number[][] };
    const vec = eD.embeddings?.[0];
    if (!vec?.length) return [];
    const sR = await fetch(`${QDRANT_URL}/collections/${RAG_COLLECTION}/points/search`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ vector: vec, limit: 5, with_payload: true }), signal: AbortSignal.timeout(5000) });
    if (!sR.ok) return [];
    const sD = await sR.json() as { result?: Array<{ score: number; payload?: Record<string, unknown> }> };
    const docs = (sD.result || []).filter(r => r.score > 0.3).map(r => { const p = r.payload || {}; return `[${p.source || ""}] ${(p.text || p.content || "") as string}`; }).filter(Boolean);
    if (docs.length < 2) { const web = await webSearch(query); if (web.length) return [...docs, "--- web ---", ...web]; }
    return docs;
  } catch { return []; }
}

function injectRag(messages: Array<{ role: string; content: string }>, chunks: string[]) {
  if (!chunks.length) return;
  const ctx = `\n\nContexte documentaire:\n${chunks.join("\n---\n")}\n\nUtilise ces informations si pertinent.`;
  const si = messages.findIndex(m => m.role === "system");
  if (si >= 0) messages[si].content += ctx;
  else messages.unshift({ role: "system", content: `Tu es un assistant IA.${ctx}` });
}

// OpenAI-compatible /v1/chat/completions (Suite Conversations)
app.post("/v1/chat/completions", async (c) => {
  const body = await c.req.json();
  const model = body.model || "mistral:7b";
  const msgs: Array<{ role: string; content: string }> = [...(body.messages || [])];
  const last = [...msgs].reverse().find(m => m.role === "user");
  if (last) injectRag(msgs, await ragSearch(last.content));
  const r = await fetch(`${ollamaFor(model)}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model, messages: msgs, stream: false }), signal: AbortSignal.timeout(TIMEOUT) });
  if (!r.ok) return c.json({ error: `Ollama ${r.status}` }, 502);
  const d = await r.json() as { message?: { content?: string } };
  return c.json({ id: `chatcmpl-${Date.now()}`, object: "chat.completion", created: Math.floor(Date.now() / 1000), model, choices: [{ index: 0, message: { role: "assistant", content: d.message?.content || "" }, finish_reason: "stop" }], usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 } });
});

// GET /v1/models
app.get("/v1/models", (c) => c.json({ object: "list", data: [{ id: "albert", object: "model", owned_by: "mascarade" }, { id: "mistral:7b", object: "model", owned_by: "mascarade" }, { id: "qwen3:4b", object: "model", owned_by: "mascarade" }, { id: "devstral", object: "model", owned_by: "mascarade" }] }));

// Electropilote /api/ai/chat (er-ops sidebar)
app.post("/api/ai/chat", async (c) => {
  const body = await c.req.json();
  const model = body.model || "mistral:7b";
  const msgs: Array<{ role: string; content: string }> = [...(body.messages || [])];
  const isStream = body.stream !== false;
  if (body.rag !== false) { const last = [...msgs].reverse().find(m => m.role === "user"); if (last) injectRag(msgs, await ragSearch(last.content)); }
  const r = await fetch(`${ollamaFor(model)}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model, messages: msgs, stream: isStream }), signal: AbortSignal.timeout(TIMEOUT) });
  if (!r.ok) return c.json({ error: `Ollama ${r.status}` }, 502);
  if (isStream && r.body) { c.header("Content-Type", "text/event-stream"); c.header("Cache-Control", "no-cache"); return c.body(r.body as ReadableStream); }
  return c.json(await r.json());
});

// GET /agents/list
app.get("/agents/list", (c) => {
  const agents = AGENTS.map(a => ({ name: a.name, description: a.description, category: a.category, capabilities: a.capabilities, model: a.preferred_model, cluster: a.cluster }));
  return c.json({ agents, count: agents.length });
});

// POST /agents/invoke
app.post("/agents/invoke", async (c) => {
  const body = await c.req.json();
  const agentName = body.agent;
  const msgs: Array<{ role: string; content: string }> = body.messages || [];
  if (!agentName) return c.json({ error: "Missing: agent" }, 400);
  if (!msgs.length) return c.json({ error: "Missing: messages" }, 400);
  const agent = AGENTS.find(a => a.name === agentName);
  if (!agent) return c.json({ error: `Agent not found: ${agentName}` }, 404);
  const model = (agent.preferred_model || "mistral:7b") as string;
  const temp = (agent.temperature ?? 0.3) as number;
  const full = [{ role: "system", content: agent.system_prompt as string }, ...msgs];
  const last = [...msgs].reverse().find(m => m.role === "user");
  if (last) injectRag(full, await ragSearch(last.content));
  try {
    const r = await fetch(`${ollamaFor(model)}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model, messages: full, stream: false, options: { temperature: temp } }), signal: AbortSignal.timeout(TIMEOUT) });
    if (!r.ok) return c.json({ error: `Ollama ${r.status}` }, 502);
    const d = await r.json() as { message?: { content?: string } };
    return c.json({ agent: agentName, model, content: d.message?.content || "", category: agent.category });
  } catch (e) { return c.json({ error: (e as Error).message, agent: agentName }, 504); }
});

// POST /openburo/ai/chat (Electropilote Open Buro)
app.post("/openburo/ai/chat", async (c) => {
  const body = await c.req.json();
  const msgs: Array<{ role: string; content: string }> = [...(body.messages || [])];
  const model = body.model || "mistral:7b";
  const agentHint = body.agent as string | undefined;
  if (agentHint) {
    const agent = AGENTS.find(a => a.name === agentHint);
    if (agent) {
      const m = (agent.preferred_model || model) as string;
      const full = [{ role: "system", content: agent.system_prompt as string }, ...msgs];
      const last = [...msgs].reverse().find(x => x.role === "user");
      if (last) injectRag(full, await ragSearch(last.content));
      try {
        const r = await fetch(`${ollamaFor(m)}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: m, messages: full, stream: false }), signal: AbortSignal.timeout(TIMEOUT) });
        if (!r.ok) return c.json({ error: `Ollama ${r.status}` }, 502);
        const d = await r.json() as { message?: { content?: string } };
        return c.json({ agent: agentHint, content: d.message?.content || "", model: m, rag: true });
      } catch (e) { return c.json({ error: (e as Error).message }, 504); }
    }
  }
  const last = [...msgs].reverse().find(m => m.role === "user");
  if (last) { const c2 = await ragSearch(last.content); if (c2.length) msgs.unshift({ role: "system", content: `Tu es Electropilote.\n\nContexte:\n${c2.join("\n---\n")}` }); else msgs.unshift({ role: "system", content: "Tu es Electropilote, l'assistant IA souverain." }); }
  try {
    const r = await fetch(`${ollamaFor(model)}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model, messages: msgs, stream: false }), signal: AbortSignal.timeout(TIMEOUT) });
    if (!r.ok) return c.json({ error: `Ollama ${r.status}` }, 502);
    const d = await r.json() as { message?: { content?: string } };
    return c.json({ agent: "electropilote", content: d.message?.content || "", model, rag: true });
  } catch (e) { return c.json({ error: (e as Error).message }, 504); }
});

// POST /api/ai/rag/index + GET /api/ai/rag/stats
app.post("/api/ai/rag/index", async (c) => {
  const docs: Array<{ text: string; source?: string }> = (await c.req.json()).documents || [];
  if (!docs.length) return c.json({ error: "No documents" }, 400);
  let indexed = 0;
  for (const doc of docs) {
    try {
      const eR = await fetch(`${ollamaFor("bge-m3")}/api/embed`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: EMBED_MODEL, input: doc.text }), signal: AbortSignal.timeout(TIMEOUT) });
      if (!eR.ok) continue;
      const vec = ((await eR.json()) as { embeddings?: number[][] }).embeddings?.[0];
      if (!vec) continue;
      await fetch(`${QDRANT_URL}/collections/${RAG_COLLECTION}/points`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ points: [{ id: Date.now() + indexed, vector: vec, payload: { text: doc.text, source: doc.source || "" } }] }) });
      indexed++;
    } catch {}
  }
  return c.json({ indexed, total: docs.length });
});
app.get("/api/ai/rag/stats", async (c) => {
  try { const r = await fetch(`${QDRANT_URL}/collections/${RAG_COLLECTION}`); const d = await r.json() as { result?: { points_count?: number } }; return c.json({ collection: RAG_COLLECTION, points: d.result?.points_count || 0 }); }
  catch (e) { return c.json({ error: (e as Error).message }, 502); }
});

// Open Buro API (direct handlers to avoid sub-app priority issues)
import { APP_REGISTRY } from "./routes/openburo.js";
import { openburoEvents } from "./routes/openburo-events.js";
import { BUSINESS_OBJECT_SCHEMAS } from "./routes/openburo-objects.js";
import { connectors } from "./routes/openburo-connectors.js";
import { workspaces } from "./routes/openburo-workspaces.js";
import { search } from "./routes/openburo-search.js";


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


// Open Buro: Workspaces (cross-app project aggregation)
app.get("/openburo/workspaces", (c) => workspaces.fetch(new Request("http://x/"), c.env));
app.post("/openburo/workspaces", async (c) => workspaces.fetch(new Request("http://x/", { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body }), c.env));
app.get("/openburo/workspaces/:id", (c) => workspaces.fetch(new Request("http://x/" + c.req.param("id")), c.env));
app.put("/openburo/workspaces/:id", async (c) => workspaces.fetch(new Request("http://x/" + c.req.param("id"), { method: "PUT", headers: c.req.raw.headers, body: c.req.raw.body }), c.env));
app.post("/openburo/workspaces/:id/resources", async (c) => workspaces.fetch(new Request("http://x/" + c.req.param("id") + "/resources", { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body }), c.env));

// Open Buro: Unified Search (Qdrant + event bus fallback)
app.get("/openburo/search", (c) => {
  const url = new URL("http://x/");
  for (const [k, v] of Object.entries(c.req.query())) url.searchParams.set(k, v as string);
  return search.fetch(new Request(url));
});
app.post("/openburo/search/index", async (c) => search.fetch(new Request("http://x/index", { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body })));
app.get("/openburo/search/stats", (c) => search.fetch(new Request("http://x/stats")));

// Open Buro: Connectors (Dolibarr, Grist, N8N webhooks)
app.post("/openburo/connectors/grist/webhook", async (c) => {
  const req = new Request("http://x/grist/webhook" + (c.req.query("doc") ? "?doc=" + c.req.query("doc") : ""), { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body });
  return connectors.fetch(req);
});
app.post("/openburo/connectors/dolibarr/webhook", async (c) => {
  return connectors.fetch(new Request("http://x/dolibarr/webhook", { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body }));
});
app.post("/openburo/connectors/n8n/webhook", async (c) => {
  return connectors.fetch(new Request("http://x/n8n/webhook", { method: "POST", headers: c.req.raw.headers, body: c.req.raw.body }));
});
app.get("/openburo/connectors/status", async (c) => {
  return connectors.fetch(new Request("http://x/status"));
});

// Open Buro: Notifications → ntfy
app.post("/openburo/notifications", async (c) => {
  const body = await c.req.json();
  if (!body.title) return c.json({ error: "Missing: title" }, 400);
  
  const ntfyUrl = process.env.NTFY_URL || "http://192.168.0.119:2586";
  const topic = body.topic || "openburo";
  
  try {
    await fetch(ntfyUrl + "/" + topic, {
      method: "POST",
      headers: {
        "Title": body.title,
        "Priority": body.priority || "default",
        "Tags": body.tags || "openburo",
        "Authorization": "Bearer tk_4u9yWK9Ij43Yhh5E2w6eKUJ7nnD7Q",
        ...(body.click ? { "Click": body.click } : {}),
      },
      body: body.message || body.title,
    });
    return c.json({ sent: true, topic });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

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
