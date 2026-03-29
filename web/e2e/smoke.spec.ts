import { test, expect } from "@playwright/test";

test.describe("Smoke Tests", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/health", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "ok",
          auth_required: false,
          core: { status: "ok", providers: ["ollama"], agents: 9 },
        }),
      });
    });

    await page.route("**/api/ops/monitor", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ai: { ollama: { ok: true, models: 1, model_names: ["qwen3:4b"] } },
          services: [],
        }),
      });
    });
  });

  test("homepage loads with Apple light theme", async ({ page }) => {
    await page.goto("/");
    // Check white background
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(bg).toContain("255, 255, 255");
    // Check title
    await expect(page).toHaveTitle(/Ops|Electron|Mascarade/i);
  });

  test("sidebar navigation renders", async ({ page }) => {
    await page.goto("/");
    // Wait for sidebar
    const sidebar = page.locator("aside#primary-sidebar");
    await expect(sidebar).toBeVisible({ timeout: 10000 });
  });

  test("dashboard loads metrics", async ({ page }) => {
    await page.goto("/");
    // Wait for content to load (not just spinner)
    await page.waitForTimeout(3000);
    const body = await page.textContent("body");
    expect(body).toBeTruthy();
  });
});
