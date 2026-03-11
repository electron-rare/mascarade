import type { Context, Next } from "hono";

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

const store = new Map<string, RateLimitEntry>();

const WINDOW_MS = 60_000;
const MAX_REQUESTS = parseInt(process.env.RATE_LIMIT_RPM || "60", 10);
const MAX_STORE_SIZE = 100_000;
const TRUST_PROXY = /^(1|true|yes)$/i.test(String(process.env.RATE_LIMIT_TRUST_PROXY || "").trim());
const TRUST_PROXY_MODE = String(process.env.RATE_LIMIT_TRUST_PROXY_MODE || "auto").trim().toLowerCase();

function firstForwardedFor(value: string | undefined): string {
  if (!value) {
    return "";
  }
  return value.split(",")[0]?.trim() || "";
}

function normalizeIp(value: string): string {
  const trimmed = String(value || "").trim();
  const withoutMappedPrefix = trimmed.replace(/^::ffff:/i, "");
  return withoutMappedPrefix.replace(/^\[(.*)\]$/, "$1");
}

function isPrivateOrLoopbackAddress(value: string): boolean {
  const ip = normalizeIp(value).toLowerCase();
  if (!ip) {
    return false;
  }
  if (ip === "localhost" || ip === "::1") {
    return true;
  }
  if (/^127\./.test(ip)) {
    return true;
  }
  if (/^10\./.test(ip)) {
    return true;
  }
  if (/^192\.168\./.test(ip)) {
    return true;
  }
  if (/^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(ip)) {
    return true;
  }
  if (/^(fc|fd)[0-9a-f]{2}:/.test(ip)) {
    return true;
  }
  if (/^fe80:/.test(ip)) {
    return true;
  }
  return false;
}

function shouldTrustProxy(directRemote: string): boolean {
  if (!TRUST_PROXY) {
    return false;
  }
  if (TRUST_PROXY_MODE === "always") {
    return true;
  }
  if (TRUST_PROXY_MODE === "never") {
    return false;
  }
  return isPrivateOrLoopbackAddress(directRemote);
}

function getClientKey(c: Context): string {
  const env = c.env as Record<string, unknown>;
  const incoming = env["incoming"] as { remote?: { address?: string } } | undefined;
  const directRemote =
    incoming?.remote?.address ||
    (typeof env["remoteAddr"] === "string" ? (env["remoteAddr"] as string) : "");

  if (shouldTrustProxy(directRemote)) {
    return (
      c.req.header("cf-connecting-ip") ||
      c.req.header("x-real-ip") ||
      firstForwardedFor(c.req.header("x-forwarded-for")) ||
      directRemote ||
      "proxy-unknown"
    );
  }

  return directRemote || "direct";
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
