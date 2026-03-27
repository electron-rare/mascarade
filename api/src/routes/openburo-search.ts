/**
 * Open Buro — Unified Search (Phase 2/3)
 * Cross-app search via Qdrant vector DB + keyword fallback
 * Index: documents from Suite Numérique, contacts from Dolibarr, rows from Grist
 */

import { Hono } from "hono";

const search = new Hono();

const QDRANT_URL = process.env.QDRANT_URL || "http://mascarade-qdrant:6333";
const COLLECTION = "openburo-search";

// GET /openburo/search — unified cross-app search
search.get("/", async (c) => {
  const q = c.req.query("q");
  if (!q) return c.json({ error: "Missing: q (query)" }, 400);

  const app = c.req.query("app");    // filter by app
  const type = c.req.query("type");  // filter by object type
  const limit = parseInt(c.req.query("limit") || "20");

  // Try semantic search via Qdrant first
  let results: any[] = [];
  let method = "keyword";

  try {
    // Check if collection exists
    const collRes = await fetch(`${QDRANT_URL}/collections/${COLLECTION}`);
    if (collRes.ok) {
      // Use Qdrant scroll with payload filter (keyword match on text field)
      const scrollRes = await fetch(`${QDRANT_URL}/collections/${COLLECTION}/points/scroll`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          limit,
          with_payload: true,
          filter: {
            must: [
              ...(app ? [{ key: "app", match: { value: app } }] : []),
              ...(type ? [{ key: "type", match: { value: type } }] : []),
            ],
            should: [
              { key: "title", match: { text: q } },
              { key: "name", match: { text: q } },
              { key: "content", match: { text: q } },
            ],
          },
        }),
      });

      if (scrollRes.ok) {
        const data = await scrollRes.json() as any;
        results = (data.result?.points || []).map((p: any) => ({
          id: p.id,
          score: 1.0,
          ...p.payload,
        }));
        method = "qdrant-keyword";
      }
    }
  } catch {
    // Qdrant not available, fallback to event bus search
  }

  // Fallback: search in event bus
  if (results.length === 0) {
    try {
      const eventsRes = await fetch(`http://localhost:3000/openburo/events?limit=200`);
      const eventsData = await eventsRes.json() as any;

      const qLower = q.toLowerCase();
      results = eventsData.events
        .filter((e: any) => {
          const dataStr = JSON.stringify(e.data || {}).toLowerCase();
          const matchesQuery = dataStr.includes(qLower) || e.type.includes(qLower);
          const matchesApp = !app || e.source.includes(app);
          const matchesType = !type || e.type.includes(type);
          return matchesQuery && matchesApp && matchesType;
        })
        .slice(0, limit)
        .map((e: any) => ({
          id: e.id,
          type: e.type,
          source: e.source,
          subject: e.subject,
          title: e.data?.label || e.data?.name || e.data?.title || e.subject,
          data: e.data,
          time: e.time,
          score: 0.5,
        }));
      method = "event-bus-scan";
    } catch {}
  }

  return c.json({
    query: q,
    method,
    results,
    count: results.length,
    filters: { app: app || null, type: type || null },
  });
});

// POST /openburo/search/index — index a document for search
search.post("/index", async (c) => {
  const body = await c.req.json();
  if (!body.id || !body.app || !body.type) {
    return c.json({ error: "Missing: id, app, type" }, 400);
  }

  const point = {
    id: typeof body.id === "string" ? Math.abs(hashCode(body.id)) : body.id,
    payload: {
      app: body.app,
      type: body.type,
      title: body.title || "",
      name: body.name || "",
      content: body.content || "",
      url: body.url || "",
      source_id: body.id,
      indexed_at: new Date().toISOString(),
    },
    vector: body.vector || null,
  };

  try {
    // Ensure collection exists
    const collRes = await fetch(`${QDRANT_URL}/collections/${COLLECTION}`);
    if (!collRes.ok) {
      await fetch(`${QDRANT_URL}/collections/${COLLECTION}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vectors: { size: 1024, distance: "Cosine" },
          on_disk_payload: true,
        }),
      });
    }

    // Upsert point (without vector if not provided — payload-only indexing)
    if (point.vector) {
      await fetch(`${QDRANT_URL}/collections/${COLLECTION}/points`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ points: [point] }),
      });
    } else {
      // Use set_payload for text-only indexing
      await fetch(`${QDRANT_URL}/collections/${COLLECTION}/points/payload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          payload: point.payload,
          points: [point.id],
        }),
      });
    }

    return c.json({ indexed: true, id: point.id, app: body.app, type: body.type });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

// GET /openburo/search/stats — search index stats
search.get("/stats", async (c) => {
  try {
    const res = await fetch(`${QDRANT_URL}/collections/${COLLECTION}`);
    if (!res.ok) return c.json({ indexed: false, message: "Collection not yet created" });
    const data = await res.json() as any;
    return c.json({
      indexed: true,
      collection: COLLECTION,
      points: data.result?.points_count || 0,
      vectors: data.result?.vectors_count || 0,
      segments: data.result?.segments_count || 0,
    });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

// Simple string hash for deterministic IDs
function hashCode(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    const chr = s.charCodeAt(i);
    hash = ((hash << 5) - hash) + chr;
    hash |= 0;
  }
  return Math.abs(hash);
}

export { search };
