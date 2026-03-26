import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { qdrantKnowledge } from "./qdrantKnowledge.js";

function makeApp() {
  const app = new Hono();
  app.route("/api/qdrant", qdrantKnowledge);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("qdrantKnowledge routes", () => {
  it("GET /health returns Qdrant health status", async () => {
    vi.spyOn(coreClient, "qdrantHealth").mockResolvedValue({
      status: "ok",
      version: "1.8.0",
    } as any);

    const res = await makeApp().request("/api/qdrant/health");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
  });

  it("GET /collections lists all collections", async () => {
    vi.spyOn(coreClient, "qdrantListCollections").mockResolvedValue({
      collections: [{ name: "knowledge" }, { name: "memos" }],
    } as any);

    const res = await makeApp().request("/api/qdrant/collections");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.collections).toHaveLength(2);
  });

  it("GET /collections/:name returns collection details", async () => {
    vi.spyOn(coreClient, "qdrantGetCollection").mockResolvedValue({
      name: "knowledge",
      vectors_count: 1024,
    } as any);

    const res = await makeApp().request("/api/qdrant/collections/knowledge");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.name).toBe("knowledge");
  });

  it("POST /collections/:name/search performs vector search", async () => {
    vi.spyOn(coreClient, "qdrantSearch").mockResolvedValue({
      result: [
        { id: 1, score: 0.95, payload: { text: "matching doc" } },
      ],
    } as any);

    const res = await makeApp().request("/api/qdrant/collections/knowledge/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vector: [0.1, 0.2, 0.3], limit: 5 }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.result).toHaveLength(1);
    expect(body.result[0].score).toBe(0.95);
  });

  it("POST /collections/:name/semantic-search performs semantic search", async () => {
    vi.spyOn(coreClient, "qdrantSemanticSearch").mockResolvedValue({
      results: [{ text: "result", score: 0.9 }],
    } as any);

    const res = await makeApp().request("/api/qdrant/collections/knowledge/semantic-search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "how to flash STM32", limit: 3 }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.results).toHaveLength(1);
  });

  it("PUT /collections/:name creates a collection", async () => {
    vi.spyOn(coreClient, "qdrantCreateCollection").mockResolvedValue({
      status: "created",
    } as any);

    const res = await makeApp().request("/api/qdrant/collections/new-collection", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vectors: { size: 384, distance: "Cosine" } }),
    });

    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.status).toBe("created");
  });

  it("DELETE /collections/:name deletes a collection", async () => {
    vi.spyOn(coreClient, "qdrantDeleteCollection").mockResolvedValue({
      status: "deleted",
    } as any);

    const res = await makeApp().request("/api/qdrant/collections/old-collection", {
      method: "DELETE",
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("deleted");
  });

  it("returns 502 when core is unreachable", async () => {
    vi.spyOn(coreClient, "qdrantHealth").mockRejectedValue(new Error("ECONNREFUSED"));

    const res = await makeApp().request("/api/qdrant/health");

    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.error).toBe("Core service unreachable");
  });
});
