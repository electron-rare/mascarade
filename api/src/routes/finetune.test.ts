import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { finetune } from "./finetune.js";

function makeApp() {
  const app = new Hono();
  app.route("/api/finetune", finetune);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("finetune routes", () => {
  it("POST /pipeline triggers a finetune pipeline via core", async () => {
    vi.spyOn(coreClient, "finetunePipeline").mockResolvedValue({
      status: "started",
      job_id: "ft-123",
    } as any);

    const res = await makeApp().request("/api/finetune/pipeline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: "code-review", domain: "stm32" }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("started");
    expect(coreClient.finetunePipeline).toHaveBeenCalledWith({
      task: "code-review",
      domain: "stm32",
    });
  });

  it("POST /pipeline rejects missing task field", async () => {
    const res = await makeApp().request("/api/finetune/pipeline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    expect(res.status).toBe(400);
  });

  it("GET /stack returns the finetune stack recommendation", async () => {
    vi.spyOn(coreClient, "finetuneStack").mockResolvedValue({
      stack: ["Unsloth", "SimPO"],
      recommended: "Unsloth + SimPO",
    } as any);

    const res = await makeApp().request("/api/finetune/stack");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.stack).toBeDefined();
    expect(Array.isArray(body.stack)).toBe(true);
  });

  it("GET /stack returns fallback when core is unreachable", async () => {
    vi.spyOn(coreClient, "finetuneStack").mockRejectedValue(new Error("ECONNREFUSED"));

    const res = await makeApp().request("/api/finetune/stack");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.recommended).toContain("Unsloth");
  });

  it("DELETE /logs/:name deletes a finetune log", async () => {
    vi.spyOn(coreClient, "deleteFinetuneLog").mockResolvedValue({ status: "deleted" } as any);

    const res = await makeApp().request("/api/finetune/logs/run-2024-01-01", {
      method: "DELETE",
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("deleted");
  });

  it("DELETE /logs/:name rejects path traversal", async () => {
    const res = await makeApp().request("/api/finetune/logs/..%2Fetc%2Fpasswd", {
      method: "DELETE",
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe("Missing log name");
  });
});
