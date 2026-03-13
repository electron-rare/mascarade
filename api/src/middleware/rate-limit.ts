import type { Context, Next } from "hono";
import type { AuthUser } from "../lib/auth.js";

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

interface MultiWindowEntry {
  minute: RateLimitEntry;
  hour: RateLimitEntry;
  day: RateLimitEntry;
}

const store = new Map<string, MultiWindowEntry>();

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * 60_000;
const DAY_MS = 24 * 60 * 60_000;
const DEFAULT_MAX_REQUESTS = parseInt(process.env.RATE_LIMIT_RPM || "60", 10);
const MAX_STORE_SIZE = 100_000;

function getClientKey(c: Context): string {
  // Try to get user from context first (set by auth middleware)
  const user = c.get("user") as AuthUser | undefined;
  if (user?.id) {
    return `user:${user.id}`;
  }

  // Fallback to IP-based key for unauthenticated requests
  return (
    `ip:${c.req.header("x-forwarded-for")?.split(",")[0]?.trim() || c.req.header("x-real-ip") || "unknown"}`
  );
}

function getUserRateLimits(c: Context): {
  perMinute: number | null;
  perHour: number | null;
  perDay: number | null;
} {
  const user = c.get("user") as AuthUser | undefined;
  const limits = user?.rate_limits;

  return {
    perMinute: limits?.requests_per_minute ?? null,
    perHour: limits?.requests_per_hour ?? null,
    perDay: limits?.requests_per_day ?? null,
  };
}

function getOrCreateEntry(key: string, now: number): MultiWindowEntry {
  let entry = store.get(key);
  if (!entry) {
    entry = {
      minute: { count: 0, resetAt: now + MINUTE_MS },
      hour: { count: 0, resetAt: now + HOUR_MS },
      day: { count: 0, resetAt: now + DAY_MS },
    };
    store.set(key, entry);
  }
  return entry;
}

export async function rateLimitMiddleware(c: Context, next: Next) {
  const key = getClientKey(c);
  const now = Date.now();

  // Check store size before processing
  if (!store.has(key) && store.size >= MAX_STORE_SIZE) {
    // Evict expired entries first
    for (const [k, v] of store) {
      if (
        now >= v.minute.resetAt &&
        now >= v.hour.resetAt &&
        now >= v.day.resetAt
      ) {
        store.delete(k);
      }
    }
    if (store.size >= MAX_STORE_SIZE) {
      return c.json({ error: "Too many requests" }, 429);
    }
  }

  const entry = getOrCreateEntry(key, now);
  const limits = getUserRateLimits(c);

  // Reset windows if expired
  if (now >= entry.minute.resetAt) {
    entry.minute = { count: 0, resetAt: now + MINUTE_MS };
  }
  if (now >= entry.hour.resetAt) {
    entry.hour = { count: 0, resetAt: now + HOUR_MS };
  }
  if (now >= entry.day.resetAt) {
    entry.day = { count: 0, resetAt: now + DAY_MS };
  }

  // Increment counters
  entry.minute.count++;
  entry.hour.count++;
  entry.day.count++;

  // Determine effective limits (use user limits if available, otherwise fallback)
  const effectiveMinuteLimit = limits.perMinute ?? DEFAULT_MAX_REQUESTS;
  const effectiveHourLimit = limits.perHour;
  const effectiveDayLimit = limits.perDay;

  // Set response headers (use minute limit for primary headers)
  c.header("X-RateLimit-Limit", String(effectiveMinuteLimit));
  c.header("X-RateLimit-Remaining", String(Math.max(0, effectiveMinuteLimit - entry.minute.count)));
  c.header("X-RateLimit-Reset", String(Math.ceil(entry.minute.resetAt / 1000)));

  // Check per-minute limit
  if (effectiveMinuteLimit !== null && entry.minute.count > effectiveMinuteLimit) {
    return c.json({
      error: "Too many requests",
      limit: "requests_per_minute",
      retry_after: Math.ceil((entry.minute.resetAt - now) / 1000),
    }, 429);
  }

  // Check per-hour limit
  if (effectiveHourLimit !== null && entry.hour.count > effectiveHourLimit) {
    return c.json({
      error: "Too many requests",
      limit: "requests_per_hour",
      retry_after: Math.ceil((entry.hour.resetAt - now) / 1000),
    }, 429);
  }

  // Check per-day limit
  if (effectiveDayLimit !== null && entry.day.count > effectiveDayLimit) {
    return c.json({
      error: "Too many requests",
      limit: "requests_per_day",
      retry_after: Math.ceil((entry.day.resetAt - now) / 1000),
    }, 429);
  }

  await next();
}

// Periodic cleanup of expired entries
setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of store) {
    // Only delete if all windows are expired
    if (
      now >= entry.minute.resetAt &&
      now >= entry.hour.resetAt &&
      now >= entry.day.resetAt
    ) {
      store.delete(key);
    }
  }
}, MINUTE_MS);
