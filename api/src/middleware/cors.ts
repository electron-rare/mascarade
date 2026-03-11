import { cors } from "hono/cors";

const rawOrigins = (process.env.CORS_ORIGINS || "")
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);
const allowAnyOrigin = rawOrigins.includes("*");

function isValidCorsOrigin(origin: string): boolean {
  try {
    const url = new URL(origin);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

const allowedOrigins = allowAnyOrigin
  ? []
  : Array.from(new Set(rawOrigins.filter((origin) => isValidCorsOrigin(origin))));
const allowedOriginSet = new Set(allowedOrigins);
const credentialsEnabled = !allowAnyOrigin && allowedOrigins.length > 0;

// Fail-closed: if CORS_ORIGINS is not set, only same-origin requests are allowed.
// Set CORS_ORIGINS=* explicitly to allow all origins (dev only).
export const corsMiddleware = cors({
  origin: (requestOrigin) => {
    if (allowAnyOrigin) {
      return "*";
    }
    if (!requestOrigin) {
      return "";
    }
    return allowedOriginSet.has(requestOrigin) ? requestOrigin : "";
  },
  allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  allowHeaders: ["Content-Type", "Authorization"],
  credentials: credentialsEnabled,
  maxAge: 3600,
});
