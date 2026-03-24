import { test, expect } from "@playwright/test";

/**
 * Tests E2E — Auth gateway sécurité
 * Vérifie les mécanismes :
 *  - Fail-closed (503) sans token
 *  - 401 avec un token invalide
 *  - 200 avec le bon token
 *  - 403 pour les routes admin avec un rôle insuffisant
 */

const VALID_TOKEN = "mock-valid-token-32chars-test";
const INVALID_TOKEN = "wrong-token-that-should-fail";
const OPERATOR_TOKEN = "mock-operator-token-32chars";

const PROTECTED_ROUTES = [
  { method: "GET", path: "/api/agents" },
  { method: "GET", path: "/api/agents/providers" },
  { method: "GET", path: "/api/ops/monitor" },
];

test.describe("Auth — fail-closed (sans token)", () => {
  for (const route of PROTECTED_ROUTES) {
    test(`${route.method} ${route.path} retourne 503 sans token`, async ({ request }) => {
      const res = await request.fetch(route.path, { method: route.method });
      expect(res.status()).toBe(503);

      const body = await res.json();
      expect(body.error).toMatch(/non configuree|non configuré/i);
    });
  }
});

test.describe("Auth — token invalide", () => {
  for (const route of PROTECTED_ROUTES) {
    test(`${route.method} ${route.path} retourne 401 avec un token invalide`, async ({ request }) => {
      const res = await request.fetch(route.path, {
        method: route.method,
        headers: { Authorization: `Bearer ${INVALID_TOKEN}` },
      });
      expect(res.status()).toBe(401);

      const body = await res.json();
      expect(body.error).toBeDefined();
    });
  }
});

test.describe("Auth — token valide", () => {
  for (const route of PROTECTED_ROUTES) {
    test(`${route.method} ${route.path} retourne 200 avec le bon token`, async ({ request }) => {
      const res = await request.fetch(route.path, {
        method: route.method,
        headers: { Authorization: `Bearer ${VALID_TOKEN}` },
      });
      expect(res.status()).toBe(200);
    });
  }
});

test.describe("Auth — RBAC admin", () => {
  test("GET /api/users retourne 403 pour un opérateur", async ({ request }) => {
    const res = await request.get("/api/users", {
      headers: { Authorization: `Bearer ${OPERATOR_TOKEN}` },
    });
    // L'opérateur n'a pas accès à la gestion des utilisateurs
    expect([403, 401]).toContain(res.status());
  });

  test("GET /api/users retourne 200 pour un admin", async ({ request }) => {
    const res = await request.get("/api/users", {
      headers: { Authorization: `Bearer ${VALID_TOKEN}` },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
  });

  test("GET /api/users retourne 503 sans token (fail-closed)", async ({ request }) => {
    const res = await request.get("/api/users");
    expect(res.status()).toBe(503);
  });
});
