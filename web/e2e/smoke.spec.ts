import { test, expect } from "@playwright/test";

test.describe("Smoke Tests", () => {
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
    const sidebar = page.locator("nav, [class*='sidebar'], aside").first();
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
