import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { llmProviders } from "./llmProviders.js";

function makeApp() {
  const app = new Hono();
  app.route("/api/v2/llm-providers", llmProviders);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
  delete process.env.ROUTELLM_CHEAP_PROVIDER;
  delete process.env.ROUTELLM_CHEAP_MODEL;
  delete process.env.ROUTELLM_STRONG_PROVIDER;
  delete process.env.ROUTELLM_STRONG_MODEL;
});

describe("llm providers route", () => {
  it("publishes health plus cheap/strong lanes", async () => {
    process.env.ROUTELLM_CHEAP_PROVIDER = "ollama";
    process.env.ROUTELLM_CHEAP_MODEL = "qwen3.5:9b";
    process.env.ROUTELLM_STRONG_PROVIDER = "claude";
    process.env.ROUTELLM_STRONG_MODEL = "claude-sonnet-4-6";

    vi.spyOn(coreClient, "health").mockResolvedValue({
      status: "ok",
      providers: ["ollama", "claude"],
      agents: 12,
    });
    vi.spyOn(coreClient, "providersStatus").mockResolvedValue({
      providers: [
        {
          name: "ollama",
          label: "Ollama",
          configured: true,
          active: true,
          fields: [],
          default_model: "qwen3.5:9b",
          models: ["qwen3.5:9b"],
        },
        {
          name: "claude",
          label: "Claude",
          configured: true,
          active: true,
          fields: [],
          default_model: "claude-sonnet-4-6",
          models: ["claude-sonnet-4-6"],
        },
      ] as any,
    });

    const res = await makeApp().request("/api/v2/llm-providers");
    const payload = await res.json();

    expect(res.status).toBe(200);
    expect(payload).toEqual({
      ok: true,
      data: {
        healthy: true,
        providers: [
          {
            lane: "cheap",
            provider: "ollama",
            model: "qwen3.5:9b",
            status: "active",
          },
          {
            lane: "strong",
            provider: "claude",
            model: "claude-sonnet-4-6",
            status: "active",
          },
        ],
        available_providers: [
          {
            name: "ollama",
            label: "Ollama",
            active: true,
            configured: true,
            default_model: "qwen3.5:9b",
            models: ["qwen3.5:9b"],
          },
          {
            name: "claude",
            label: "Claude",
            active: true,
            configured: true,
            default_model: "claude-sonnet-4-6",
            models: ["claude-sonnet-4-6"],
          },
        ],
        total: 2,
      },
    });
  });
});
