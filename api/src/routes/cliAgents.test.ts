import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { cliAgents } from "./cliAgents.js";

function makeApp() {
  const app = new Hono();
  app.route("/v1/api/cli-agents", cliAgents);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("cli agents routes", () => {
  it("forwards run requests to core", async () => {
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
    });
  });

  it("returns 500 when core client throws a non-CoreApiError", async () => {
    vi.spyOn(coreClient, "runCliAgent").mockRejectedValue(new Error("network failure"));

    const res = await makeApp().request("/v1/api/cli-agents/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent: "vibe",
        prompt: "Fix the failing test",
      }),
    });

    expect(res.status).toBe(500);
    const body = await res.json();
    expect(body.error).toBe("Internal server error");
  });

  it("forwards CoreApiError status from core", async () => {
    const { CoreApiError } = await import("../client/core.js");
    vi.spyOn(coreClient, "runCliAgent").mockRejectedValue(
      new CoreApiError("Validation failed", 400, { detail: "bad input" }),
    );

    const res = await makeApp().request("/v1/api/cli-agents/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent: "unknown",
        prompt: "",
      }),
    });

    expect(res.status).toBe(400);
  });
});
