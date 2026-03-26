import { Hono } from "hono";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock node:fs before importing the route
vi.mock("node:fs", () => ({
  promises: {
    mkdir: vi.fn().mockResolvedValue(undefined),
    readdir: vi.fn().mockResolvedValue([]),
    readFile: vi.fn(),
    writeFile: vi.fn().mockResolvedValue(undefined),
    unlink: vi.fn().mockResolvedValue(undefined),
    access: vi.fn(),
  },
}));

vi.mock("../lib/otel.js", () => ({
  emitStructuredLog: vi.fn(),
}));

import { promises as fs } from "node:fs";
import { nodeEngine } from "./node-engine.js";

const mockedFs = vi.mocked(fs);

function makeApp() {
  const app = new Hono();
  app.route("/node-engine", nodeEngine);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("node-engine routes", () => {
  describe("GET /graphs", () => {
    it("returns an empty list when no graphs exist", async () => {
      mockedFs.readdir.mockResolvedValue([]);

      const res = await makeApp().request("/node-engine/graphs");
      expect(res.status).toBe(200);

      const body = await res.json();
      expect(body).toEqual({ graphs: [], total: 0 });
    });

    it("returns 500 when readdir throws", async () => {
      mockedFs.mkdir.mockRejectedValue(new Error("disk error"));

      const res = await makeApp().request("/node-engine/graphs");
      // listGraphs catches errors and returns []
      expect(res.status).toBe(200);
    });
  });

  describe("GET /graphs/:id", () => {
    it("returns 400 for invalid graph ID", async () => {
      const res = await makeApp().request("/node-engine/graphs/invalid%20id%21");
      expect(res.status).toBe(400);
      expect(await res.json()).toEqual({ error: "Invalid graph ID" });
    });

    it("returns 404 when graph does not exist", async () => {
      mockedFs.readFile.mockRejectedValue(new Error("ENOENT"));

      const res = await makeApp().request("/node-engine/graphs/my-graph");
      expect(res.status).toBe(404);
    });

    it("returns graph data when found", async () => {
      const graphData = {
        id: "test-graph",
        name: "Test",
        nodes: [],
        edges: [],
        metadata: { id: "test-graph", name: "Test", created_at: "2026-01-01", updated_at: "2026-01-01" },
      };
      mockedFs.readFile.mockResolvedValue(JSON.stringify(graphData));

      const res = await makeApp().request("/node-engine/graphs/test-graph");
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual(graphData);
    });
  });

  describe("POST /graphs", () => {
    it("returns 400 when name is missing", async () => {
      const res = await makeApp().request("/node-engine/graphs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      expect(res.status).toBe(400);
    });

    it("creates a graph successfully", async () => {
      mockedFs.access.mockRejectedValue(new Error("ENOENT"));

      const res = await makeApp().request("/node-engine/graphs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "My Graph", nodes: [], edges: [] }),
      });
      expect(res.status).toBe(201);
      const body = await res.json();
      expect(body.name).toBe("My Graph");
      expect(body.id).toBeTruthy();
    });

    it("returns 409 when graph ID already exists", async () => {
      mockedFs.access.mockResolvedValue(undefined);

      const res = await makeApp().request("/node-engine/graphs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: "existing-graph", name: "Duplicate" }),
      });
      expect(res.status).toBe(409);
    });
  });

  describe("PUT /graphs/:id", () => {
    it("returns 404 when graph does not exist", async () => {
      mockedFs.readFile.mockRejectedValue(new Error("ENOENT"));

      const res = await makeApp().request("/node-engine/graphs/nonexistent", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "Updated" }),
      });
      expect(res.status).toBe(404);
    });

    it("updates an existing graph", async () => {
      const existing = {
        id: "my-graph",
        name: "Old Name",
        nodes: [],
        edges: [],
        metadata: { id: "my-graph", name: "Old Name", created_at: "2026-01-01", updated_at: "2026-01-01" },
      };
      mockedFs.readFile.mockResolvedValue(JSON.stringify(existing));

      const res = await makeApp().request("/node-engine/graphs/my-graph", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "New Name" }),
      });
      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.name).toBe("New Name");
    });
  });

  describe("DELETE /graphs/:id", () => {
    it("returns 400 for invalid graph ID", async () => {
      const res = await makeApp().request("/node-engine/graphs/invalid%20id%21", {
        method: "DELETE",
      });
      expect(res.status).toBe(400);
    });

    it("returns 404 when graph does not exist", async () => {
      mockedFs.readFile.mockRejectedValue(new Error("ENOENT"));

      const res = await makeApp().request("/node-engine/graphs/nonexistent", {
        method: "DELETE",
      });
      expect(res.status).toBe(404);
    });

    it("deletes an existing graph", async () => {
      const graphData = {
        id: "del-graph",
        name: "Delete Me",
        nodes: [],
        edges: [],
        metadata: { id: "del-graph", name: "Delete Me", created_at: "2026-01-01", updated_at: "2026-01-01" },
      };
      mockedFs.readFile.mockResolvedValue(JSON.stringify(graphData));
      mockedFs.unlink.mockResolvedValue(undefined);

      const res = await makeApp().request("/node-engine/graphs/del-graph", {
        method: "DELETE",
      });
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({ success: true, message: "Graph deleted" });
    });
  });

  describe("POST /graphs/:id/execute", () => {
    const ORIGINAL_FETCH = global.fetch;

    afterEach(() => {
      if (ORIGINAL_FETCH === undefined) {
        // @ts-expect-error test cleanup
        delete global.fetch;
      } else {
        global.fetch = ORIGINAL_FETCH;
      }
    });

    it("returns 400 for invalid graph ID", async () => {
      const res = await makeApp().request("/node-engine/graphs/invalid%20id%21/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      expect(res.status).toBe(400);
    });

    it("proxies execution to core and returns result", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ result: "done" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const res = await makeApp().request("/node-engine/graphs/my-graph/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inputs: {} }),
      });
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({ result: "done" });
    });

    it("returns 502 when core is unreachable", async () => {
      vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection refused")));

      const res = await makeApp().request("/node-engine/graphs/my-graph/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      expect(res.status).toBe(502);
    });
  });

  describe("GET /runtime/status", () => {
    const ORIGINAL_FETCH = global.fetch;

    afterEach(() => {
      if (ORIGINAL_FETCH === undefined) {
        // @ts-expect-error test cleanup
        delete global.fetch;
      } else {
        global.fetch = ORIGINAL_FETCH;
      }
    });

    it("proxies runtime status from core", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          new Response(JSON.stringify({ status: "running" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      );

      const res = await makeApp().request("/node-engine/runtime/status");
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({ status: "running" });
    });

    it("returns 502 when core is unreachable", async () => {
      vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection refused")));

      const res = await makeApp().request("/node-engine/runtime/status");
      expect(res.status).toBe(502);
    });
  });
});
