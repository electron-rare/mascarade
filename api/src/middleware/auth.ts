/**
 * Middleware d'authentification — Bearer token avec validation database et comparaison timing-safe.
 * Si DATABASE_URL est configuree, valide contre la base de donnees.
 * Sinon, utilise MASCARADE_API_KEY (backward compatibility).
 * Si aucune auth n'est configuree, desactive l'auth (warning au demarrage).
 */

import { timingSafeEqual } from "node:crypto";
import type { MiddlewareHandler } from "hono";
import { isDatabaseAuthAvailable, validateToken } from "../lib/auth.js";

const API_KEY_COOKIE = "mascarade_key";

function configuredApiKeys(): string[] {
  return (process.env.MASCARADE_API_KEY || "")
    .split(",")
    .map((key) => key.trim())
    .filter((key) => key.length >= 16);
}

const useDatabaseAuth = isDatabaseAuthAvailable();

if (!useDatabaseAuth && configuredApiKeys().length === 0) {
  console.warn(
    "[auth] Neither DATABASE_URL nor MASCARADE_API_KEY configured — all protected routes are PUBLIC",
  );
} else if (useDatabaseAuth) {
  console.info("[auth] Using database-backed authentication");
} else {
  console.info("[auth] Using legacy MASCARADE_API_KEY authentication");
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
  // Extract token from header or cookie
  const authHeader = c.req.header("Authorization");
  const headerToken =
    authHeader && authHeader.startsWith("Bearer ")
      ? authHeader.slice(7)
      : null;
  const cookieToken = tokenFromCookie(c.req.header("Cookie"));
  const token = headerToken || cookieToken;

  if (!token) {
    // No token provided
    if (useDatabaseAuth || configuredApiKeys().length > 0) {
      return c.json({ error: "Token invalide ou manquant" }, 401);
    }
    // No auth configured, allow through
    return next();
  }

  // Validate token
  let isValid = false;

  if (useDatabaseAuth) {
    // Database-backed authentication
    try {
      const user = await validateToken(token);
      if (user) {
        isValid = true;
        // Attach user to context for downstream use
        c.set("user", user);
      }
    } catch (error) {
      // Token validation failed
      isValid = false;
    }
  } else {
    // Legacy env variable authentication (backward compatibility)
    const apiKeys = configuredApiKeys();
    if (apiKeys.length === 0) {
      // No auth configured
      return next();
    }
    isValid = apiKeys.some((apiKey) => safeEqual(token, apiKey));
  }

  if (!isValid) {
    return c.json({ error: "Token invalide ou manquant" }, 401);
  }

  return next();
};
