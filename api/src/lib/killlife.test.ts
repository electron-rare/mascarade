import { describe, expect, it } from "vitest";
import { assertSafeWorkflowId, validateWorkflowDocument } from "./killlife.js";

describe("assertSafeWorkflowId", () => {
  it("accepts a normalized safe slug", () => {
    expect(assertSafeWorkflowId("embedded-ci-local")).toBe("embedded-ci-local");
  });

  it("rejects traversal-like identifiers", () => {
    expect(() => assertSafeWorkflowId("../escape")).toThrow(/Invalid workflow id/);
  });
});

describe("validateWorkflowDocument", () => {
  it("accepts a minimal local workflow", () => {
    const result = validateWorkflowDocument({
      id: "demo-local",
      title: "Demo Local",
      category: "demo",
      version: 1,
      status: "ready",
      execution_modes: ["local"],
      viewport: { width: 1200, height: 720 },
      nodes: [
        {
          id: "start",
          type: "note",
          label: "Start",
          x: 20,
          y: 20,
          runner: { kind: "none" },
        },
        {
          id: "validate",
          type: "local-action",
          label: "Validate",
          x: 180,
          y: 20,
          runner: { kind: "local-action", action: "compliance.validate" },
        },
      ],
      edges: [{ id: "start-validate", source: "start", target: "validate" }],
    });

    expect(result.valid).toBe(true);
    expect(result.schema_errors).toEqual([]);
    expect(result.semantic_errors).toEqual([]);
  });

  it("rejects cycles and unknown node references", () => {
    const result = validateWorkflowDocument({
      id: "bad-demo",
      title: "Bad Demo",
      category: "demo",
      version: 1,
      status: "ready",
      execution_modes: ["local"],
      viewport: { width: 1200, height: 720 },
      nodes: [
        {
          id: "node-a",
          type: "local-action",
          label: "A",
          x: 20,
          y: 20,
          runner: { kind: "local-action", action: "compliance.validate" },
        },
        {
          id: "node-b",
          type: "local-action",
          label: "B",
          x: 180,
          y: 20,
          runner: { kind: "local-action", action: "ci.audit" },
        },
      ],
      edges: [
        { id: "node-a-node-b", source: "node-a", target: "node-b" },
        { id: "node-b-node-a", source: "node-b", target: "node-a" },
        { id: "node-b-missing", source: "node-b", target: "missing" },
      ],
    });

    expect(result.valid).toBe(false);
    expect(result.semantic_errors.join(" ")).toMatch(/cycle/i);
    expect(result.semantic_errors.join(" ")).toMatch(/does not exist/);
  });
});
