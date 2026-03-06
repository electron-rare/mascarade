/**
 * Middleware d'authentification — Bearer token avec comparaison timing-safe.
 * Si MASCARADE_API_KEY est vide, l'auth est desactivee (warning au demarrage).
 */

import { timingSafeEqual } from "node:crypto";
import type { MiddlewareHandler } from "hono";

function configuredApiKeys(): string[] {
  return (process.env.MASCARADE_API_KEY || "")
    .split(",")
    .map((key) => key.trim())
    .filter((key) => key.length >= 8);
}

if (configuredApiKeys().length === 0) {
  console.warn(
    "[auth] MASCARADE_API_KEY not set — all protected routes are PUBLIC",
  );
}

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  return timingSafeEqual(Buffer.from(a), Buffer.from(b));
}

export const authMiddleware: MiddlewareHandler = async (c, next) => {
  const apiKeys = configuredApiKeys();
  if (apiKeys.length === 0) {
    return next();
  }

  const authHeader = c.req.header("Authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return c.json({ error: "Token invalide ou manquant" }, 401);
  }

  const token = authHeader.slice(7);
  const isValid = apiKeys.some((apiKey) => safeEqual(token, apiKey));
  if (!isValid) {
    return c.json({ error: "Token invalide ou manquant" }, 401);
  }
  return next();
};
