import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { providers } from "./providers.js";

function makeApp() {
  const app = new Hono();
  app.route("/v1/api/providers", providers);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("providers routes", () => {
  it("forwards codestral FIM requests to core", async () => {
    vi.spyOn(coreClient, "codestralFillInMiddle").mockResolvedValue({
      content: "    return total\n",
      model: "codestral-latest",
      provider: "codestral",
      usage: {},
    });

    const res = await makeApp().request("/v1/api/providers/codestral/fim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: "def add(a, b):\n",
        suffix: "\nresult = add(1, 2)\n",
        max_tokens: 64,
      }),
    });

    expect(res.status).toBe(200);
    expect(coreClient.codestralFillInMiddle).toHaveBeenCalledWith({
      prompt: "def add(a, b):\n",
      suffix: "\nresult = add(1, 2)\n",
      temperature: 0,
      max_tokens: 64,
    });
  });

  it("rejects requests with invalid JSON body", async () => {
    const res = await makeApp().request("/v1/api/providers/codestral/fim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "not-json{",
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Validation failed");
  });

  it("rejects requests missing required prompt field", async () => {
    const res = await makeApp().request("/v1/api/providers/codestral/fim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suffix: "some suffix" }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Validation failed");
    expect(body.details).toBeDefined();
  });

  it("returns 502 when core is unreachable", async () => {
    vi.spyOn(coreClient, "codestralFillInMiddle").mockRejectedValue(new Error("ECONNREFUSED"));

    const res = await makeApp().request("/v1/api/providers/codestral/fim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: "def add(a, b):\n",
        suffix: "\n",
      }),
    });

    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.error).toBe("Core service unreachable");
  });
});
