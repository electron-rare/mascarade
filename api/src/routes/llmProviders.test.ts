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

  it("returns 502 when core is unreachable", async () => {
    vi.spyOn(coreClient, "health").mockRejectedValue(new Error("ECONNREFUSED"));
    vi.spyOn(coreClient, "providersStatus").mockRejectedValue(new Error("ECONNREFUSED"));

    const res = await makeApp().request("/api/v2/llm-providers");

    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.error).toBe("Core service unreachable");
  });

  it("reports lane as unavailable when provider is not in the list", async () => {
    process.env.ROUTELLM_CHEAP_PROVIDER = "nonexistent";
    process.env.ROUTELLM_CHEAP_MODEL = "model-x";
    process.env.ROUTELLM_STRONG_PROVIDER = "claude";
    process.env.ROUTELLM_STRONG_MODEL = "claude-sonnet-4-6";

    vi.spyOn(coreClient, "health").mockResolvedValue({
      status: "ok",
      providers: ["claude"],
      agents: 5,
    });
    vi.spyOn(coreClient, "providersStatus").mockResolvedValue({
      providers: [
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
    const cheapLane = payload.data.providers.find((p: any) => p.lane === "cheap");
    expect(cheapLane.status).toBe("unavailable");
  });

  it("uses default env values when ROUTELLM env vars are not set", async () => {
    vi.spyOn(coreClient, "health").mockResolvedValue({
      status: "ok",
      providers: ["ollama"],
      agents: 3,
    });
    vi.spyOn(coreClient, "providersStatus").mockResolvedValue({
      providers: [] as any,
    });

    const res = await makeApp().request("/api/v2/llm-providers");
    const payload = await res.json();

    expect(res.status).toBe(200);
    const cheapLane = payload.data.providers.find((p: any) => p.lane === "cheap");
    expect(cheapLane.provider).toBe("ollama");
    expect(cheapLane.model).toBe("qwen3.5:9b");
  });
});
