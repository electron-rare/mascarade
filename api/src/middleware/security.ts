/**
 * Middleware de headers de securite HTTP.
 */

import type { MiddlewareHandler } from "hono";

export const securityHeaders: MiddlewareHandler = async (c, next) => {
  await next();
  c.header("X-Content-Type-Options", "nosniff");
  c.header("X-Frame-Options", "DENY");
  c.header("X-XSS-Protection", "0");
  c.header("Referrer-Policy", "strict-origin-when-cross-origin");
  c.header(
    "Content-Security-Policy",
    "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:",
  );
};
