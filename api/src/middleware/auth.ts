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
const MIN_KEY_LEN = 16;
const PERSIST_MAX_AGE = 30 * 24 * 3600; // 30 days

type AuthRole = "viewer" | "operator" | "admin";
const ROLE_RANK: Record<AuthRole, number> = {
  viewer: 1,
  operator: 2,
  admin: 3,
};

function configuredApiKeys(): string[] {
  return (process.env.MASCARADE_API_KEY || "")
    .split(",")
    .map((key) => key.trim())
    .filter((key) => key.length >= MIN_KEY_LEN);
}

function configuredRoleKeys(envName: string): string[] {
  return (process.env[envName] || "")
    .split(",")
    .map((key) => key.trim())
    .filter((key) => key.length >= MIN_KEY_LEN);
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

export function makeSessionCookie(token: string, persist: boolean, secure: boolean): string {
  const secureAttr = secure ? "; Secure" : "";
  const maxAge = persist ? `; Max-Age=${PERSIST_MAX_AGE}` : "";
  return `${API_KEY_COOKIE}=${encodeURIComponent(token)}; HttpOnly; SameSite=Strict; Path=/${secureAttr}${maxAge}`;
}

export function clearSessionCookie(secure: boolean): string {
  const secureAttr = secure ? "; Secure" : "";
  return `${API_KEY_COOKIE}=; HttpOnly; SameSite=Strict; Path=/${secureAttr}; Max-Age=0`;
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

export function isValidConfiguredApiKey(rawToken: string): boolean {
  const token = rawToken.trim();
  if (!token || token.length < MIN_KEY_LEN) {
    return false;
  }
  const apiKeys = configuredApiKeys();
  return apiKeys.some((apiKey) => safeEqual(token, apiKey));
}

function requiredRoleForRequest(method: string, path: string): AuthRole {
  const normalizedMethod = method.toUpperCase();
  const normalizedPath = path.toLowerCase();
  const readOnly =
    normalizedMethod === "GET" ||
    normalizedMethod === "HEAD" ||
    normalizedMethod === "OPTIONS";

  if (
    normalizedPath.startsWith("/api/settings/runtime-secrets") ||
    normalizedPath.startsWith("/api/settings/providers") ||
    normalizedPath.startsWith("/api/settings/oauth") ||
    normalizedPath.startsWith("/api/mcp/industrial") ||
    normalizedPath.startsWith("/api/ops") ||
    normalizedPath.startsWith("/api/cluster/forward")
  ) {
    return "admin";
  }

  if (
    normalizedPath.startsWith("/api/cluster") ||
    normalizedPath.startsWith("/api/p2p") ||
    normalizedPath.startsWith("/api/killlife")
  ) {
    return readOnly ? "viewer" : "operator";
  }

  if (readOnly) {
    return "viewer";
  }
  return "operator";
}

function resolveRole(token: string): AuthRole | null {
  const adminKeys = configuredRoleKeys("MASCARADE_RBAC_ADMIN_KEYS");
  const operatorKeys = configuredRoleKeys("MASCARADE_RBAC_OPERATOR_KEYS");
  const viewerKeys = configuredRoleKeys("MASCARADE_RBAC_VIEWER_KEYS");
  const rbacEnabled =
    /^(1|true|yes)$/i.test(String(process.env.MASCARADE_RBAC_ENABLED || "").trim()) ||
    adminKeys.length > 0 ||
    operatorKeys.length > 0 ||
    viewerKeys.length > 0;

  if (!rbacEnabled) {
    return "admin";
  }
  if (adminKeys.some((key) => safeEqual(token, key))) {
    return "admin";
  }
  if (operatorKeys.some((key) => safeEqual(token, key))) {
    return "operator";
  }
  if (viewerKeys.some((key) => safeEqual(token, key))) {
    return "viewer";
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

  const role = resolveRole(token);
  if (!role) {
    return c.json({ error: "Role non assigne pour ce token" }, 403);
  }
  const requiredRole = requiredRoleForRequest(c.req.method.toUpperCase(), c.req.path);
  if (ROLE_RANK[role] < ROLE_RANK[requiredRole]) {
    return c.json({ error: "Permissions insuffisantes" }, 403);
  }

  return next();
};
