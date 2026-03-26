import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/killlife.js", () => ({
  listWorkflows: vi.fn(),
  getWorkflow: vi.fn(),
  saveWorkflow: vi.fn(),
  validateWorkflowDocument: vi.fn(),
  runWorkflow: vi.fn(),
  listWorkflowRuns: vi.fn(),
  listEvidence: vi.fn(),
}));

import {
  listWorkflows,
  getWorkflow,
  saveWorkflow,
  validateWorkflowDocument,
  runWorkflow,
  listWorkflowRuns,
  listEvidence,
} from "../lib/killlife.js";
import { killlife } from "./killlife.js";

function makeApp() {
  const app = new Hono();
  app.route("/api/killlife", killlife);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("killlife routes", () => {
  it("GET /workflows lists all workflows", async () => {
    vi.mocked(listWorkflows).mockResolvedValue([
      { id: "wf-1", name: "Build Firmware", nodes: [] },
    ] as any);

    const res = await makeApp().request("/api/killlife/workflows");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.workflows).toHaveLength(1);
    expect(body.root).toBeDefined();
  });

  it("GET /workflows/:id returns a workflow with validation and runs", async () => {
    const mockWorkflow = { id: "wf-1", name: "Build Firmware", nodes: [] };
    vi.mocked(getWorkflow).mockResolvedValue(mockWorkflow as any);
    vi.mocked(validateWorkflowDocument).mockReturnValue({ valid: true, errors: [] } as any);
    vi.mocked(listWorkflowRuns).mockResolvedValue([]);

    const res = await makeApp().request("/api/killlife/workflows/wf-1");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.workflow.id).toBe("wf-1");
    expect(body.validation.valid).toBe(true);
  });

  it("GET /workflows/:id returns 404 when workflow not found", async () => {
    vi.mocked(getWorkflow).mockRejectedValue(new Error("Workflow not found"));

    const res = await makeApp().request("/api/killlife/workflows/nonexistent");

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe("Workflow not found");
  });

  it("PUT /workflows/:id saves a workflow", async () => {
    vi.mocked(saveWorkflow).mockResolvedValue({ status: "saved", id: "wf-1" } as any);

    const res = await makeApp().request("/api/killlife/workflows/wf-1", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Updated Workflow", nodes: [] }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("saved");
  });

  it("POST /workflows/:id/run executes a workflow", async () => {
    vi.mocked(runWorkflow).mockResolvedValue({
      status: "completed",
      run_id: "run-1",
    } as any);

    const res = await makeApp().request("/api/killlife/workflows/wf-1/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "local", dry_run: false }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("completed");
  });

  it("GET /evidence/:target lists evidence for a target", async () => {
    vi.mocked(listEvidence).mockResolvedValue([
      { type: "file", path: "/evidence/report.pdf" },
    ] as any);

    const res = await makeApp().request("/api/killlife/evidence/firmware-v2");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.evidence).toHaveLength(1);
  });
});
