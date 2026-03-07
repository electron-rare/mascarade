/**
 * Middleware d'authentification — Bearer token avec comparaison timing-safe.
 * Si MASCARADE_API_KEY est vide, l'auth est desactivee (warning au demarrage).
 */

import { timingSafeEqual } from "node:crypto";
import type { MiddlewareHandler } from "hono";

const API_KEY_COOKIE = "mascarade_key";

function configuredApiKeys(): string[] {
  return (process.env.MASCARADE_API_KEY || "")
    .split(",")
    .map((key) => key.trim())
    .filter((key) => key.length >= 16);
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

function tokenFromCookie(cookieHeader?: string): string | null {
  if (!cookieHeader) {
    return null;
  }

  const cookies = cookieHeader.split(";");
  for (const part of cookies) {
    const [rawName, ...rawValueParts] = part.trim().split("=");
    if (rawName !== API_KEY_COOKIE) {
      continue;
    }

    const rawValue = rawValueParts.join("=");
    if (!rawValue) {
      return null;
    }

    try {
      return decodeURIComponent(rawValue);
    } catch {
      return rawValue;
    }
  }

  return null;
}

export const authMiddleware: MiddlewareHandler = async (c, next) => {
  const apiKeys = configuredApiKeys();
  if (apiKeys.length === 0) {
    return next();
  }

  const authHeader = c.req.header("Authorization");
  const headerToken =
    authHeader && authHeader.startsWith("Bearer ")
      ? authHeader.slice(7)
      : null;
  const cookieToken = tokenFromCookie(c.req.header("Cookie"));
  const token = headerToken || cookieToken;

  if (!token) {
    return c.json({ error: "Token invalide ou manquant" }, 401);
  }

  const isValid = apiKeys.some((apiKey) => safeEqual(token, apiKey));
  if (!isValid) {
    return c.json({ error: "Token invalide ou manquant" }, 401);
  }
  return next();
};
