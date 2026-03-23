import { Hono } from "hono";
import { describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { cliAgents } from "./cliAgents.js";

function makeApp() {
  const app = new Hono();
  app.route("/v1/api/cli-agents", cliAgents);
  return app;
}

describe("cli agents routes", () => {
  it("forwards status requests to core", async () => {
    vi.spyOn(coreClient, "cliAgentsStatus").mockResolvedValue({
      agents: {
        vibe: {
          available: true,
          binary: "vibe",
          provider: "Mistral (Devstral)",
          modes: ["chat", "fim"],
        },
        codex: {
          available: true,
          binary: "codex",
          provider: "OpenAI (o4-mini)",
          modes: ["exec", "review"],
        },
        "claude-code": {
          available: false,
          binary: "claude",
          provider: "Anthropic (Sonnet/Opus)",
          modes: ["print", "interactive"],
        },
      },
    });

    const res = await makeApp().request("/v1/api/cli-agents/status");

    expect(res.status).toBe(200);
    expect(coreClient.cliAgentsStatus).toHaveBeenCalledTimes(1);
  });

  it("forwards validated run requests to core", async () => {
    vi.spyOn(coreClient, "runCliAgent").mockResolvedValue({
      agent: "vibe",
      content: "patched successfully",
      model: "devstral-small-2505",
      provider: "vibe",
      usage: { input_tokens: 10, output_tokens: 20, total_tokens: 30 },
    });

    const res = await makeApp().request("/v1/api/cli-agents/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent: "vibe",
        prompt: "Fix the failing test",
        workdir: "/tmp/demo",
        max_turns: 3,
      }),
    });

    expect(res.status).toBe(200);
    expect(coreClient.runCliAgent).toHaveBeenCalledWith({
      agent: "vibe",
      prompt: "Fix the failing test",
      workdir: "/tmp/demo",
      max_turns: 3,
      max_price: 2,
      model: "sonnet",
      full_auto: true,
    });
  });

  it("rejects invalid request bodies", async () => {
    const res = await makeApp().request("/v1/api/cli-agents/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent: "unknown",
        prompt: "",
      }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Validation failed");
  });
});
