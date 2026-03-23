import { Hono } from "hono";
import { describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { models } from "./models.js";

function makeApp() {
  const app = new Hono();
  app.route("/api/v1/models", models);
  return app;
}

describe("models routes", () => {
  it("publishes an OpenAI-style catalog built from provider status", async () => {
    vi.spyOn(coreClient, "providersStatus").mockResolvedValue({
      providers: [
        {
          name: "openai",
          label: "OpenAI",
          configured: true,
          active: true,
          fields: [],
          default_model: "openai:gpt-4.1-mini",
          models: ["openai:gpt-4.1-mini", "openai:gpt-4.1"],
        },
        {
          name: "ollama",
          label: "Ollama",
          configured: true,
          active: true,
          fields: [],
          default_model: "qwen3.5:9b",
          models: ["qwen3.5:9b", "openai:gpt-4.1-mini"],
        },
        {
          name: "claude",
          label: "Claude",
          configured: true,
          active: false,
          fields: [],
          default_model: "claude-sonnet-4-6",
          models: ["claude-sonnet-4-6"],
        },
      ] as any,
    });

    const res = await makeApp().request("/api/v1/models");
    const payload = await res.json();

    expect(res.status).toBe(200);
    expect(payload).toEqual({
      object: "list",
      data: [
        {
          id: "auto",
          object: "model",
          created: 0,
          owned_by: "mascarade",
          provider: "mascarade",
          providers: ["ollama", "openai", "claude"],
          active: true,
          configured: true,
          default: true,
        },
        {
          id: "auto:strong",
          object: "model",
          created: 0,
          owned_by: "mascarade",
          provider: "mascarade",
          providers: ["ollama", "openai", "claude"],
          active: true,
          configured: true,
          default: false,
        },
        {
          id: "auto:cheap",
          object: "model",
          created: 0,
          owned_by: "mascarade",
          provider: "mascarade",
          providers: ["ollama", "openai", "claude"],
          active: true,
          configured: true,
          default: false,
        },
        {
          id: "auto:fast",
          object: "model",
          created: 0,
          owned_by: "mascarade",
          provider: "mascarade",
          providers: ["ollama", "openai", "claude"],
          active: true,
          configured: true,
          default: false,
        },
        {
          id: "openai:gpt-4.1-mini",
          object: "model",
          created: 0,
          owned_by: "ollama",
          provider: "ollama",
          providers: ["ollama", "openai"],
          active: true,
          configured: true,
          default: true,
        },
        {
          id: "qwen3.5:9b",
          object: "model",
          created: 0,
          owned_by: "ollama",
          provider: "ollama",
          providers: ["ollama"],
          active: true,
          configured: true,
          default: true,
        },
        {
          id: "claude-sonnet-4-6",
          object: "model",
          created: 0,
          owned_by: "claude",
          provider: "claude",
          providers: ["claude"],
          active: false,
          configured: true,
          default: true,
        },
        {
          id: "openai:gpt-4.1",
          object: "model",
          created: 0,
          owned_by: "openai",
          provider: "openai",
          providers: ["openai"],
          active: true,
          configured: true,
          default: false,
        },
      ],
    });
  });
});
