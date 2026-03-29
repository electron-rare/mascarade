import { Hono } from "hono";
import { ollamaFor, AGENTS, QDRANT_URL, RAG_COLLECTION, EMBED_MODEL, TIMEOUT } from "../lib/ai-config.js";
import { ragSearch, injectRag } from "../lib/rag.js";

const ai = new Hono();

// OpenAI-compatible /v1/chat/completions (Suite Conversations)
ai.post("/v1/chat/completions", async (c) => {
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
ai.get("/v1/models", (c) => c.json({ object: "list", data: [{ id: "albert", object: "model", owned_by: "mascarade" }, { id: "mistral:7b", object: "model", owned_by: "mascarade" }, { id: "qwen3:4b", object: "model", owned_by: "mascarade" }, { id: "devstral", object: "model", owned_by: "mascarade" }] }));

// Electropilote /api/ai/chat (er-ops sidebar)
ai.post("/api/ai/chat", async (c) => {
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
ai.get("/agents/list", (c) => {
  const agents = AGENTS.map(a => ({ name: a.name, description: a.description, category: a.category, capabilities: a.capabilities, model: a.preferred_model, cluster: a.cluster }));
  return c.json({ agents, count: agents.length });
});

// POST /agents/invoke
ai.post("/agents/invoke", async (c) => {
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
ai.post("/openburo/ai/chat", async (c) => {
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
ai.post("/api/ai/rag/index", async (c) => {
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

ai.get("/api/ai/rag/stats", async (c) => {
  try { const r = await fetch(`${QDRANT_URL}/collections/${RAG_COLLECTION}`); const d = await r.json() as { result?: { points_count?: number } }; return c.json({ collection: RAG_COLLECTION, points: d.result?.points_count || 0 }); }
  catch (e) { return c.json({ error: (e as Error).message }, 502); }
});

export { ai };
