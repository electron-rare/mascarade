/**
 * Middleware d'authentification — Bearer token avec validation database et comparaison timing-safe.
 * Si DATABASE_URL est configuree, valide contre la base de donnees.
 * Sinon, utilise MASCARADE_API_KEY (backward compatibility).
 * Si aucune auth n'est configuree, fail-closed par defaut sauf opt-out explicite.
 */

import { timingSafeEqual } from "node:crypto";
import type { MiddlewareHandler } from "hono";
import type { AuthUser } from "../lib/auth.js";
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

// Computed once at startup for logging, but isAuthConfigured() re-checks at runtime
const useDatabaseAuthAtStartup = isDatabaseAuthAvailable();

function allowPublicApi(): boolean {
  return /^(1|true|yes)$/i.test(String(process.env.MASCARADE_ALLOW_PUBLIC_API || "").trim());
}

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

export function isAuthConfigured(): boolean {
  return isDatabaseAuthAvailable() || configuredApiKeys().length > 0;
}

export { allowPublicApi };

if (!isAuthConfigured()) {
  if (allowPublicApi()) {
    console.warn(
      "[auth] Authentication is not configured, but MASCARADE_ALLOW_PUBLIC_API=true keeps protected routes public",
    );
  } else {
    console.error(
      "[auth] Authentication is not configured — protected routes will fail closed until DATABASE_URL or MASCARADE_API_KEY is set",
    );
  }
} else if (useDatabaseAuthAtStartup) {
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
  const apiKeys = configuredApiKeys();
  if (apiKeys.length === 0) return true; // Auth disabled
  const token = rawToken.trim();
  if (!token || token.length < MIN_KEY_LEN) {
    return false;
  }
  return apiKeys.some((apiKey) => safeEqual(token, apiKey));
}

export function authUnavailableResponse(): { error: string } {
  return { error: "Authentification non configuree" };
}

function requiredRoleForRequest(method: string, path: string): AuthRole {
  const normalizedMethod = method.toUpperCase();
  const normalizedPath = path.toLowerCase();
  const readOnly =
    normalizedMethod === "GET" ||
    normalizedMethod === "HEAD" ||
    normalizedMethod === "OPTIONS";

  if (normalizedPath.startsWith("/api/ops")) {
    return readOnly ? "viewer" : "admin";
  }

  if (
    normalizedPath.startsWith("/api/settings/runtime-secrets") ||
    normalizedPath.startsWith("/api/settings/providers") ||
    normalizedPath.startsWith("/api/settings/oauth") ||
    normalizedPath.startsWith("/api/mcp/industrial") ||
    normalizedPath.startsWith("/api/cluster/forward") ||
    normalizedPath.startsWith("/api/users")
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

function roleFromUser(user: AuthUser | undefined): AuthRole | null {
  if (!user) {
    return null;
  }

  switch (user.role_id) {
    case 1:
      return "admin";
    case 2:
      return "operator";
    case 3:
      return "viewer";
    default:
      return null;
  }
}

function resolveRole(token: string, user?: AuthUser): AuthRole | null {
  const userRole = roleFromUser(user);
  if (userRole) {
    return userRole;
  }

  const adminKeys = configuredRoleKeys("MASCARADE_RBAC_ADMIN_KEYS");
  const operatorKeys = configuredRoleKeys("MASCARADE_RBAC_OPERATOR_KEYS");
  const viewerKeys = configuredRoleKeys("MASCARADE_RBAC_VIEWER_KEYS");

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
  const authHeader = c.req.header("Authorization");
  const headerToken =
    authHeader && authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : null;
  const cookieToken = tokenFromCookie(c.req.header("Cookie"));
  const token = headerToken || cookieToken;

  if (!token) {
    if (isAuthConfigured()) {
      return c.json({ error: "Token invalide ou manquant" }, 401);
    }
    if (allowPublicApi()) {
      return next();
    }
    return c.json(authUnavailableResponse(), 503);
  }

  let isValid = false;
  let user: AuthUser | undefined;

  if (isDatabaseAuthAvailable()) {
    try {
      const validatedUser = await validateToken(token);
      if (validatedUser) {
        isValid = true;
        user = validatedUser;
        c.set("user", validatedUser);
      }
    } catch {
      isValid = false;
    }
  } else {
    if (!isAuthConfigured()) {
      if (allowPublicApi()) {
        return next();
      }
      return c.json(authUnavailableResponse(), 503);
    }
    isValid = isValidConfiguredApiKey(token);
  }

  if (!isValid) {
    return c.json({ error: "Token invalide ou manquant" }, 401);
  }

  const role = resolveRole(token, user);
  if (!role) {
    return c.json({ error: "Role non assigne pour ce token" }, 403);
  }

  const requiredRole = requiredRoleForRequest(c.req.method, c.req.path);
  if (ROLE_RANK[role] < ROLE_RANK[requiredRole]) {
    return c.json({ error: "Permissions insuffisantes" }, 403);
  }

  return next();
};
