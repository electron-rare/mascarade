import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/otel.js", () => ({
  emitStructuredLog: vi.fn(),
}));

import { nodes, graphs } from "./nodes.js";

function makeNodesApp() {
  const app = new Hono();
  app.route("/nodes", nodes);
  return app;
}

function makeGraphsApp() {
  const app = new Hono();
  app.route("/graphs", graphs);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("nodes catalog routes", () => {
  describe("GET /catalog", () => {
    it("returns empty catalog structure", async () => {
      const res = await makeNodesApp().request("/nodes/catalog");
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({
        node_types: [],
        domains: [],
        total_count: 0,
      });
    });
  });

  describe("GET /catalog/:domain", () => {
    it("returns empty catalog for any domain", async () => {
      const res = await makeNodesApp().request("/nodes/catalog/industrial");
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({
        node_types: [],
        domains: [],
        total_count: 0,
      });
    });
  });
});

describe("graphs CRUD routes", () => {
  describe("POST /", () => {
    it("creates a graph with a name", async () => {
      const res = await makeGraphsApp().request("/graphs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "Test Graph" }),
      });
      expect(res.status).toBe(201);
      const body = await res.json();
      expect(body.name).toBe("Test Graph");
      expect(body.id).toBeTruthy();
      expect(body.status).toBe("draft");
    });

    it("returns 400 when name is missing", async () => {
      const res = await makeGraphsApp().request("/graphs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      expect(res.status).toBe(400);
      expect(await res.json()).toEqual({ error: "Graph name is required" });
    });
  });

  describe("GET /", () => {
    it("returns all graphs", async () => {
      const app = makeGraphsApp();

      // Create a graph first
      await app.request("/graphs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "Listed Graph" }),
      });

      const res = await app.request("/graphs");
      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.graphs).toBeInstanceOf(Array);
      expect(body.total_count).toBeGreaterThanOrEqual(1);
    });
  });

  describe("GET /:id", () => {
    it("returns 404 for non-existent graph", async () => {
      const res = await makeGraphsApp().request("/graphs/nonexistent-id");
      expect(res.status).toBe(404);
      expect(await res.json()).toEqual({ error: "Graph not found" });
    });
  });

  describe("PUT /:id", () => {
    it("returns 404 when graph does not exist", async () => {
      const res = await makeGraphsApp().request("/graphs/nonexistent", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "Updated" }),
      });
      expect(res.status).toBe(404);
    });
  });

  describe("DELETE /:id", () => {
    it("returns 404 when graph does not exist", async () => {
      const res = await makeGraphsApp().request("/graphs/nonexistent", {
        method: "DELETE",
      });
      expect(res.status).toBe(404);
    });
  });
});
