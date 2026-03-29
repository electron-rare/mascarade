import { ollamaFor, QDRANT_URL, SEARXNG_URL, RAG_COLLECTION, EMBED_MODEL, TIMEOUT } from "./ai-config.js";

export async function webSearch(query: string): Promise<string[]> {
  try {
    const r = await fetch(`${SEARXNG_URL}/search?${new URLSearchParams({ q: query, format: "json", language: "fr" })}`, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) return [];
    const d = await r.json() as { results?: Array<{ title?: string; url?: string; content?: string }> };
    return (d.results || []).slice(0, 3).map(r => `[${r.title}](${r.url}): ${(r.content || "").slice(0, 200)}`).filter(Boolean);
  } catch { return []; }
}

export async function ragSearch(query: string): Promise<string[]> {
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

export function injectRag(messages: Array<{ role: string; content: string }>, chunks: string[]) {
  if (!chunks.length) return;
  const ctx = `\n\nContexte documentaire:\n${chunks.join("\n---\n")}\n\nUtilise ces informations si pertinent.`;
  const si = messages.findIndex(m => m.role === "system");
  if (si >= 0) messages[si].content += ctx;
  else messages.unshift({ role: "system", content: `Tu es un assistant IA.${ctx}` });
}
