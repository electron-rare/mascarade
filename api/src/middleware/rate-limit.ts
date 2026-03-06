import type { Context, Next } from "hono";

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

const store = new Map<string, RateLimitEntry>();

const WINDOW_MS = 60_000;
const MAX_REQUESTS = parseInt(process.env.RATE_LIMIT_RPM || "60", 10);
const MAX_STORE_SIZE = 100_000;

function getClientKey(c: Context): string {
  return (
    c.req.header("x-forwarded-for")?.split(",")[0]?.trim() ||
    c.req.header("x-real-ip") ||
    "unknown"
  );
}

export async function rateLimitMiddleware(c: Context, next: Next) {
  const key = getClientKey(c);
  const now = Date.now();

  let entry = store.get(key);
  if (!entry || now >= entry.resetAt) {
    if (!entry && store.size >= MAX_STORE_SIZE) {
      // Evict expired entries first; if still full, reject
      const cutoff = now;
      for (const [k, v] of store) {
        if (cutoff >= v.resetAt) store.delete(k);
      }
      if (store.size >= MAX_STORE_SIZE) {
        return c.json({ error: "Too many requests" }, 429);
      }
    }
    entry = { count: 0, resetAt: now + WINDOW_MS };
    store.set(key, entry);
  }

  entry.count++;

  c.header("X-RateLimit-Limit", String(MAX_REQUESTS));
  c.header("X-RateLimit-Remaining", String(Math.max(0, MAX_REQUESTS - entry.count)));
  c.header("X-RateLimit-Reset", String(Math.ceil(entry.resetAt / 1000)));

  if (entry.count > MAX_REQUESTS) {
    return c.json({ error: "Too many requests" }, 429);
  }

  await next();
}

// Periodic cleanup of expired entries
setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of store) {
    if (now >= entry.resetAt) store.delete(key);
  }
}, WINDOW_MS);
