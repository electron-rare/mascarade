import { Hono } from "hono";
import { streamSSE } from "hono/streaming";
import { createClient } from "redis";

const openburoEvents = new Hono();

// Redis connection (lazy)
let redis: ReturnType<typeof createClient> | null = null;
const STREAM_KEY = "openburo:events";

async function getRedis() {
  if (!redis) {
    redis = createClient({ url: process.env.REDIS_URL || "redis://mascarade-redis:6379/15" });
    redis.on("error", (err: Error) => console.error("[openburo/events] Redis error:", err.message));
    await redis.connect();
  }
  return redis;
}

// CloudEvents v1.0 schema
interface CloudEvent {
  specversion: "1.0";
  id: string;
  type: string;        // e.g. "contact.created", "invoice.sent"
  source: string;      // e.g. "/openburo/apps/dolibarr"
  time: string;        // ISO 8601
  subject?: string;    // e.g. contact ID
  datacontenttype?: string;
  data?: Record<string, unknown>;
}

// POST /openburo/events — publish a CloudEvent
openburoEvents.post("/", async (c) => {
  const body = await c.req.json<Partial<CloudEvent>>();

  // Validate required CloudEvents fields
  if (!body.type || !body.source) {
    return c.json({ error: "Missing required fields: type, source" }, 400);
  }

  const event: CloudEvent = {
    specversion: "1.0",
    id: body.id || crypto.randomUUID(),
    type: body.type,
    source: body.source,
    time: body.time || new Date().toISOString(),
    subject: body.subject,
    datacontenttype: body.datacontenttype || "application/json",
    data: body.data || {},
  };

  try {
    const r = await getRedis();
    await r.xAdd(STREAM_KEY, "*", {
      event: JSON.stringify(event),
    });
    return c.json({ status: "published", id: event.id, type: event.type });
  } catch (err: any) {
    return c.json({ error: "Failed to publish", detail: err.message }, 500);
  }
});

// GET /openburo/events — list recent events
openburoEvents.get("/", async (c) => {
  const limit = parseInt(c.req.query("limit") || "50");
  const type = c.req.query("type");
  const source = c.req.query("source");

  try {
    const r = await getRedis();
    const entries = await r.xRevRange(STREAM_KEY, "+", "-", { COUNT: limit * 2 });

    let events = entries.map((e: any) => ({
      stream_id: e.id,
      ...JSON.parse(e.message.event),
    }));

    if (type) events = events.filter((e: any) => e.type === type || e.type.startsWith(type + "."));
    if (source) events = events.filter((e: any) => e.source.includes(source));

    return c.json({ events: events.slice(0, limit), count: events.length });
  } catch (err: any) {
    return c.json({ error: "Failed to read events", detail: err.message }, 500);
  }
});

// GET /openburo/events/stream — SSE real-time stream
openburoEvents.get("/stream", (c) => {
  const typeFilter = c.req.query("type");

  return streamSSE(c, async (stream) => {
    const r = await getRedis();
    let lastId = "$"; // Only new events

    while (true) {
      try {
        const results = await r.xRead(
          [{ key: STREAM_KEY, id: lastId }],
          { COUNT: 10, BLOCK: 5000 }
        );

        if (results) {
          for (const result of results as any[]) {
            for (const entry of (result as any).messages) {
              const event = JSON.parse(entry.message.event);
              if (typeFilter && !event.type.startsWith(typeFilter)) continue;

              await stream.writeSSE({
                data: JSON.stringify(event),
                event: event.type,
                id: entry.id,
              });
              lastId = entry.id;
            }
          }
        }
      } catch {
        break;
      }
    }
  });
});

// GET /openburo/events/stats — event statistics
openburoEvents.get("/stats", async (c) => {
  try {
    const r = await getRedis();
    const info = await r.xInfoStream(STREAM_KEY).catch(() => null);

    if (!info) return c.json({ total: 0, types: {} });

    // Get last 1000 events for stats
    const entries = await r.xRevRange(STREAM_KEY, "+", "-", { COUNT: 1000 });
    const typeCounts: Record<string, number> = {};
    const sourceCounts: Record<string, number> = {};

    for (const e of entries) {
      const event = JSON.parse(e.message.event);
      typeCounts[event.type] = (typeCounts[event.type] || 0) + 1;
      sourceCounts[event.source] = (sourceCounts[event.source] || 0) + 1;
    }

    return c.json({
      total: info.length,
      first_entry: (info as any)["first-entry"]?.id,
      last_entry: (info as any)["last-entry"]?.id,
      types: typeCounts,
      sources: sourceCounts,
    });
  } catch (err: any) {
    return c.json({ error: err.message }, 500);
  }
});

export { openburoEvents };
