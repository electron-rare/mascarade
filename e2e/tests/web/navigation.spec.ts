import { test, expect, type Page } from "@playwright/test";

/**
 * Tests E2E — Navigation de l'application web Mascarade
 * Vérifie que le routing React fonctionne et que les pages principales se chargent.
 * Toutes les requêtes API sont interceptées via page.route().
 */

/** Stub API minimal utilisé par toutes les pages */
async function stubApiRoutes(page: Page) {
  await page.route("/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        auth_required: false,
        core: { status: "ok", providers: ["openai", "ollama"], agents: 5 },
      }),
    }),
  );

  await page.route("/api/**", (route) => {
    const url = new URL(route.request().url());

    if (url.pathname === "/api/ops/monitor") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ai: {
            ollama: {
              ok: true,
              models: 2,
              model_names: ["llama3.2", "mistral:7b"],
            },
          },
          services: {
            core: { ok: true },
            api: { ok: true },
          },
        }),
      });
    }

    if (url.pathname === "/api/agents" || url.pathname === "/api/agents/list") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { name: "agent-zero", description: "Lead agent", builtin: true },
          { name: "coder", description: "Code assistant", builtin: false },
        ]),
      });
    }

    if (url.pathname === "/api/agents/providers") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ providers: ["openai", "ollama"] }),
      });
    }

    if (url.pathname === "/api/version") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ version: "0.1.0", commit: "mock" }),
      });
    }

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });
}

test.describe("Navigation principale", () => {
  test.beforeEach(async ({ page }) => {
    await stubApiRoutes(page);
  });

  test("charge le Dashboard à la racine /", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  });

  test("navigue vers /playground", async ({ page }) => {
    await page.goto("/playground");
    await expect(page.getByText("Direct routing sandbox", { exact: false })).toBeVisible();
  });

  test("navigue vers /agents", async ({ page }) => {
    await page.goto("/agents");
    // La page agents contient "agent" dans les titres
    await expect(page.getByText("agent", { exact: false }).first()).toBeVisible();
  });

  test("navigue vers /orchestrate", async ({ page }) => {
    await page.goto("/orchestrate");
    await expect(page).toHaveURL(/\/orchestrate/);
  });

  test("navigue vers /ops", async ({ page }) => {
    await page.goto("/ops");
    await expect(page).toHaveURL(/\/ops/);
  });

  test("navigue vers /logs", async ({ page }) => {
    await page.goto("/logs");
    await expect(page).toHaveURL(/\/logs/);
  });

  test("navigue vers /metrics", async ({ page }) => {
    await page.goto("/metrics");
    await expect(page).toHaveURL(/\/metrics/);
  });

  test("navigue vers /infra", async ({ page }) => {
    await page.goto("/infra");
    await expect(page).toHaveURL(/\/infra/);
  });

  test("navigue vers /settings", async ({ page }) => {
    await page.goto("/settings");
    await expect(page).toHaveURL(/\/settings/);
  });

  test("affiche une page 404 pour une route inconnue", async ({ page }) => {
    await page.goto("/cette-route-nexiste-absolument-pas");
    await expect(page.getByText("404")).toBeVisible();
  });
});
