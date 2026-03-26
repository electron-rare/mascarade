import { test, expect } from "@playwright/test";

test.describe("Agents", () => {
  test("agents page lists agents", async ({ page }) => {
    await page.goto("/agents");
    await page.waitForTimeout(3000);
    const body = await page.textContent("body");
    // Should contain at least one known agent name
    expect(body).toMatch(/agent-zero|writer|analyst|coder|lead-scorer/i);
  });

  test("agent detail page loads", async ({ page }) => {
    await page.goto("/agents/agent-zero");
    await page.waitForTimeout(3000);
    const body = await page.textContent("body");
    expect(body).toMatch(/agent-zero|coordination|copilot/i);
  });
});
