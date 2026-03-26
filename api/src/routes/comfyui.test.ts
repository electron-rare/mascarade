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

  it("POST /workflow submits a raw workflow to core", async () => {
    vi.spyOn(coreClient, "comfyuiQueueWorkflow").mockResolvedValue({
      prompt_id: "wf-456",
      status: "queued",
    } as any);

    const workflow = { nodes: [{ id: 1, type: "KSampler" }] };
    const res = await makeApp().request("/api/comfyui/workflow", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.prompt_id).toBe("wf-456");
    expect(coreClient.comfyuiQueueWorkflow).toHaveBeenCalledWith(workflow);
  });

  it("GET /history/:promptId retrieves prompt history", async () => {
    vi.spyOn(coreClient, "comfyuiHistory").mockResolvedValue({
      prompt_id: "abc-123",
      outputs: { images: ["img_001.png"] },
    } as any);

    const res = await makeApp().request("/api/comfyui/history/abc-123");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.prompt_id).toBe("abc-123");
  });

  it("GET /history/:promptId rejects path traversal in promptId", async () => {
    const res = await makeApp().request("/api/comfyui/history/abc..123");

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid prompt ID parameter");
  });

  it("POST /interrupt stops current execution", async () => {
    vi.spyOn(coreClient, "comfyuiInterrupt").mockResolvedValue({
      ok: true,
    } as any);

    const res = await makeApp().request("/api/comfyui/interrupt", {
      method: "POST",
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
  });

  it("GET /image requires filename parameter", async () => {
    const res = await makeApp().request("/api/comfyui/image");

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("filename query parameter is required");
  });

  it("GET /image rejects path traversal in filename", async () => {
    const res = await makeApp().request("/api/comfyui/image?filename=..%2F..%2Fetc%2Fpasswd");

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Invalid path parameter");
  });
});
