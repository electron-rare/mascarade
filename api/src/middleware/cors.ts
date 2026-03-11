import { cors } from "hono/cors";

const allowedOrigins = (process.env.CORS_ORIGINS || "")
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);
const allowAnyOrigin = allowedOrigins.includes("*");
const explicitOrigins = allowAnyOrigin ? "*" : allowedOrigins;

// Fail-closed: if CORS_ORIGINS is not set, only same-origin requests are allowed.
// Set CORS_ORIGINS=* explicitly to allow all origins (dev only).
export const corsMiddleware = cors({
  origin: allowedOrigins.length > 0 ? explicitOrigins : [],
  allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  allowHeaders: ["Content-Type", "Authorization"],
  credentials: !allowAnyOrigin,
  maxAge: 3600,
});
