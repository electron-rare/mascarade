import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { orchestrateTemplates } from "./orchestrateTemplates.js";

function makeApp() {
  const app = new Hono();
  app.route("/templates", orchestrateTemplates);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("orchestrateTemplates routes", () => {
  describe("GET /", () => {
    it("lists templates from core", async () => {
      vi.spyOn(coreClient, "listTemplates").mockResolvedValue({
        templates: [{ id: "t1", name: "Summarize" }],
      } as any);

      const res = await makeApp().request("/templates");
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({
        templates: [{ id: "t1", name: "Summarize" }],
      });
    });

    it("returns error when core fails", async () => {
      vi.spyOn(coreClient, "listTemplates").mockRejectedValue(new Error("core down"));

      const res = await makeApp().request("/templates");
      expect(res.status).toBeGreaterThanOrEqual(500);
    });
  });

  describe("GET /:id", () => {
    it("returns a specific template", async () => {
      vi.spyOn(coreClient, "getTemplate").mockResolvedValue({
        id: "t1",
        name: "Summarize",
        steps: [],
      } as any);

      const res = await makeApp().request("/templates/t1");
      expect(res.status).toBe(200);
      expect(await res.json()).toMatchObject({ id: "t1" });
    });

    it("returns error when template not found", async () => {
      const err = new Error("Not found") as any;
      err.response = { status: 404 };
      vi.spyOn(coreClient, "getTemplate").mockRejectedValue(err);

      const res = await makeApp().request("/templates/nonexistent");
      expect(res.status).toBeGreaterThanOrEqual(400);
    });
  });

  describe("POST /:id/deploy", () => {
    it("deploys a template with input", async () => {
      vi.spyOn(coreClient, "deployTemplate").mockResolvedValue({
        status: "deployed",
        run_id: "run-123",
      } as any);

      const res = await makeApp().request("/templates/t1/deploy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: "summarize this" }),
      });
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({
        status: "deployed",
        run_id: "run-123",
      });
    });

    it("returns error when deploy fails", async () => {
      vi.spyOn(coreClient, "deployTemplate").mockRejectedValue(new Error("deploy failed"));

      const res = await makeApp().request("/templates/t1/deploy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: "test" }),
      });
      expect(res.status).toBeGreaterThanOrEqual(500);
    });
  });
});
