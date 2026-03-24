import { test, expect } from "@playwright/test";

/**
 * Tests E2E — Health endpoint
 * Vérifie que /health est toujours accessible (sans auth) et retourne la structure attendue.
 */
test.describe("GET /health", () => {
  test("retourne status 200 sans authentification", async ({ request }) => {
    const res = await request.get("/health");
    expect(res.status()).toBe(200);
  });

  test("retourne la structure de santé complète", async ({ request }) => {
    const res = await request.get("/health");
    const body = await res.json();

    expect(body).toMatchObject({
      status: expect.stringMatching(/^(ok|degraded)$/),
      auth_required: expect.any(Boolean),
    });
  });

  test("indique que l'auth est requise", async ({ request }) => {
    const res = await request.get("/health");
    const body = await res.json();
    expect(body.auth_required).toBe(true);
  });

  test("inclut l'état du core", async ({ request }) => {
    const res = await request.get("/health");
    const body = await res.json();
    expect(body.core).toBeDefined();
    expect(body.core.status).toBe("ok");
    expect(Array.isArray(body.core.providers)).toBe(true);
    expect(typeof body.core.agents).toBe("number");
  });

  test("Content-Type est application/json", async ({ request }) => {
    const res = await request.get("/health");
    expect(res.headers()["content-type"]).toContain("application/json");
  });
});
