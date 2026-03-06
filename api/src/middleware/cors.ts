import { cors } from "hono/cors";

const allowedOrigins = (process.env.CORS_ORIGINS || "")
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);

// Fail-closed: if CORS_ORIGINS is not set, only same-origin requests are allowed.
// Set CORS_ORIGINS=* explicitly to allow all origins (dev only).
export const corsMiddleware = cors({
  origin: allowedOrigins.length > 0 ? allowedOrigins : [],
  allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  allowHeaders: ["Content-Type", "Authorization"],
  credentials: true,
  maxAge: 3600,
});
