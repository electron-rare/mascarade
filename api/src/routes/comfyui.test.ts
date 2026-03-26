import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { CoreApiError } from "../client/core.js";
import { comfyui } from "./comfyui.js";

function makeApp() {
  const app = new Hono();
  app.route("/api/comfyui", comfyui);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("comfyui routes", () => {
  it("GET /status returns ComfyUI system status", async () => {
    vi.spyOn(coreClient, "comfyuiStatus").mockResolvedValue({
      status: "running",
      gpu: "RTX 4090",
    } as any);

    const res = await makeApp().request("/api/comfyui/status");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("running");
  });

  it("GET /queue returns the ComfyUI queue", async () => {
    vi.spyOn(coreClient, "comfyuiQueue").mockResolvedValue({
      queue_running: [],
      queue_pending: [],
    } as any);

    const res = await makeApp().request("/api/comfyui/queue");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.queue_running).toBeDefined();
  });

  it("GET /models/:modelType lists models of a given type", async () => {
    vi.spyOn(coreClient, "comfyuiModels").mockResolvedValue({
      models: ["sd_xl_base_1.0.safetensors"],
    } as any);

    const res = await makeApp().request("/api/comfyui/models/checkpoints");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.models).toBeDefined();
  });

  it("GET /models/:modelType rejects invalid model type with dots", async () => {
    const res = await makeApp().request("/api/comfyui/models/check..points");

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid model type parameter");
  });

  it("POST /generate triggers image generation", async () => {
    vi.spyOn(coreClient, "comfyuiGenerate").mockResolvedValue({
      prompt_id: "abc-123",
      status: "queued",
    } as any);

    const res = await makeApp().request("/api/comfyui/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: "a cat", width: 512, height: 512 }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.prompt_id).toBe("abc-123");
  });

  it("returns 502 when core is unreachable", async () => {
    vi.spyOn(coreClient, "comfyuiStatus").mockRejectedValue(new Error("ECONNREFUSED"));

    const res = await makeApp().request("/api/comfyui/status");

    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.error).toBe("Core service unreachable");
  });
});
