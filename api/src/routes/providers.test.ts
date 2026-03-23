import { Hono } from "hono";
import { describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { providers } from "./providers.js";

function makeApp() {
  const app = new Hono();
  app.route("/v1/api/providers", providers);
  return app;
}

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
});
