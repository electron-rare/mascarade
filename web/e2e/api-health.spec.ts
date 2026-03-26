import { test, expect } from "@playwright/test";

test.describe("API Health", () => {
  test("health endpoint returns OK", async ({ request }) => {
    const res = await request.get("/health", { headers: { Accept: "application/json" } });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.status).toBe("ok");
    const agentCount = data.core?.agents ?? data.agents ?? 0;
    expect(agentCount).toBeGreaterThan(0);
  });

  test("agents API returns list", async ({ request }) => {
    const res = await request.get("/api/agents");
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.agents.length).toBeGreaterThan(20);
    const names = data.agents.map((a: any) => a.name);
    expect(names).toContain("agent-zero");
    expect(names).toContain("lead-scorer");
  });

  test("calendar API responds", async ({ request }) => {
    const res = await request.get("/api/ops/calendar");
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toHaveProperty("events");
    expect(data).toHaveProperty("source", "calcom");
  });

  test("mail API responds", async ({ request }) => {
    const res = await request.get("/api/ops/mail");
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data).toHaveProperty("campaigns");
    expect(data).toHaveProperty("subscribers");
  });

  test("MCP endpoint responds", async ({ request }) => {
    const res = await request.get("/api/ops/mcp", { headers: { Accept: "application/json" } });
    // MCP may return 502 if ops-agent is unreachable, just check it doesnt 404
    expect([200, 502]).toContain(res.status());
  });
});
