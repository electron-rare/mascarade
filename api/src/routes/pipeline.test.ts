import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("node:child_process", () => ({
  spawn: vi.fn(() => ({ unref: vi.fn() })),
}));

vi.mock("node:fs", () => ({
  existsSync: vi.fn(),
  readFileSync: vi.fn(),
}));

import { existsSync, readFileSync } from "node:fs";
import { pipeline } from "./pipeline.js";

function makeApp() {
  const app = new Hono();
  app.route("/api/pipeline", pipeline);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("pipeline routes", () => {
  it("POST /run starts a pipeline for a valid domain", async () => {
    const res = await makeApp().request("/api/pipeline/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain: "stm32" }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("started");
    expect(body.domain).toBe("stm32");
    expect(body.run_id).toContain("pipeline-stm32-");
  });

  it("POST /run rejects invalid domain", async () => {
    const res = await makeApp().request("/api/pipeline/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain: "invalid-domain" }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBeDefined();
  });

  it("POST /run supports dry_run flag", async () => {
    const res = await makeApp().request("/api/pipeline/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain: "kicad", dry_run: true }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.dry_run).toBe(true);
  });

  it("GET /status returns idle when no state file exists", async () => {
    vi.mocked(existsSync).mockReturnValue(false);

    const res = await makeApp().request("/api/pipeline/status");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("idle");
  });

  it("GET /status returns active when state file exists", async () => {
    vi.mocked(existsSync).mockReturnValue(true);
    vi.mocked(readFileSync).mockReturnValue(
      JSON.stringify({ domain: "stm32", step: "train", progress: 0.5 }),
    );

    const res = await makeApp().request("/api/pipeline/status");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("active");
    expect(body.data.domain).toBe("stm32");
  });

  it("GET /models returns empty when no registry file exists", async () => {
    vi.mocked(existsSync).mockReturnValue(false);

    const res = await makeApp().request("/api/pipeline/models");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("empty");
  });
});
