import { test, expect } from "@playwright/test";

test.describe("Copilot", () => {
  test("agent-zero responds to a prompt", async ({ request }) => {
    const res = await request.post("/api/agents/agent-zero/run", {
      data: {
        messages: [{ role: "user", content: "Dis bonjour en une phrase." }],
        project_id: "electron-rare",
      },
    });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.content).toBeTruthy();
    expect(data.content.length).toBeGreaterThan(5);
    expect(data.provider).toBeTruthy();
  });

  test("lead-scorer returns structured JSON", { timeout: 60000 }, async ({ request }) => {
    const res = await request.post("/api/agents/lead-scorer/run", {
      data: {
        messages: [{ role: "user", content: "lead_id: TEST-E2E\nemail: test@test.com\nname: Test User\norganization: Test Corp\nsource_channel: site\nneed_type: technique\nsegment: industrie" }],
        project_id: "electron-rare",
      },
    });
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    const parsed = JSON.parse(data.content);
    expect(parsed).toHaveProperty("score");
    expect(parsed).toHaveProperty("confidence");
    expect(parsed).toHaveProperty("segment");
    expect(parsed).toHaveProperty("next_action");
    expect(typeof parsed.score).toBe("number");
  });
});
