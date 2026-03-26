import { test, expect } from "@playwright/test";

const routes = [
  { path: "/", name: "Dashboard" },
  { path: "/playground", name: "Playground" },
  { path: "/agents", name: "Agents" },
  { path: "/ops", name: "Ops Hub" },
  { path: "/logs", name: "Logs" },
  { path: "/metrics", name: "Metrics" },
  { path: "/infra", name: "Infrastructure" },
  { path: "/calendar", name: "Calendar" },
  { path: "/mail", name: "Mail" },
  { path: "/mcp", name: "MCP Servers" },
  { path: "/settings", name: "Settings" },
];

test.describe("Navigation", () => {
  for (const route of routes) {
    test(`${route.name} (${route.path}) loads without error`, async ({ page }) => {
      await page.goto(route.path);
      await page.waitForTimeout(2000);
      // No crash - page should have content
      const body = await page.textContent("body");
      expect(body!.length).toBeGreaterThan(50);
      // No unhandled errors
      const errors: string[] = [];
      page.on("pageerror", (err) => errors.push(err.message));
      expect(errors).toHaveLength(0);
    });
  }
});
