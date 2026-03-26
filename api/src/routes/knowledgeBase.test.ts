import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { knowledgeBase } from "./knowledgeBase.js";

function makeApp() {
  const app = new Hono();
  app.route("/api/knowledge-base", knowledgeBase);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("knowledge base routes", () => {
  describe("GET /search", () => {
    it("requires project_id on search", async () => {
      const res = await makeApp().request("/api/knowledge-base/search?q=musique&limit=5");

      expect(res.status).toBe(400);
      const body = await res.json();
      expect(body.error).toBe("Query validation failed");
    });

    it("forwards multi-project scope to the core search route", async () => {
      const searchSpy = vi.spyOn(coreClient, "knowledgeBaseSearch").mockResolvedValue({
        results: [],
        provider: "kxkm",
        knowledge_scope: "federated",
        federation_scope: ["project-alpha", "project-beta"],
      });

      const res = await makeApp().request(
        "/api/knowledge-base/search?q=musique&limit=5&project_id=project-alpha&federation_scope=project-alpha,project-beta&knowledge_scope=federated",
      );

      expect(res.status).toBe(200);
      expect(searchSpy).toHaveBeenCalledWith("musique", {
        limit: 5,
        projectId: "project-alpha",
        federationScope: ["project-alpha", "project-beta"],
        knowledgeScope: "federated",
      });
    });

    it("returns 502 when core is unreachable during search", async () => {
      vi.spyOn(coreClient, "knowledgeBaseSearch").mockRejectedValue(new Error("ECONNREFUSED"));

      const res = await makeApp().request(
        "/api/knowledge-base/search?q=test&limit=5&project_id=proj-1",
      );

      expect(res.status).toBe(502);
      const body = await res.json();
      expect(body.error).toBe("Core service unreachable");
    });
  });

  describe("GET /pages/:pageId", () => {
    it("reads a page by ID from core", async () => {
      vi.spyOn(coreClient, "knowledgeBaseReadPage").mockResolvedValue({
        id: "page-42",
        title: "Architecture Notes",
        content: "# Architecture\nMicroservices layout...",
      } as any);

      const res = await makeApp().request("/api/knowledge-base/pages/page-42");

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.id).toBe("page-42");
      expect(body.title).toBe("Architecture Notes");
      expect(coreClient.knowledgeBaseReadPage).toHaveBeenCalledWith("page-42");
    });

    it("returns 502 when core fails to read page", async () => {
      vi.spyOn(coreClient, "knowledgeBaseReadPage").mockRejectedValue(new Error("timeout"));

      const res = await makeApp().request("/api/knowledge-base/pages/page-99");

      expect(res.status).toBe(502);
    });
  });

  describe("POST /pages/:pageId/append", () => {
    it("appends content to an existing page", async () => {
      vi.spyOn(coreClient, "knowledgeBaseAppend").mockResolvedValue({
        ok: true,
        page_id: "page-42",
      } as any);

      const res = await makeApp().request("/api/knowledge-base/pages/page-42/append", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: "New section content" }),
      });

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.ok).toBe(true);
      expect(coreClient.knowledgeBaseAppend).toHaveBeenCalledWith("page-42", "New section content");
    });

    it("returns 502 when core fails during append", async () => {
      vi.spyOn(coreClient, "knowledgeBaseAppend").mockRejectedValue(new Error("ECONNREFUSED"));

      const res = await makeApp().request("/api/knowledge-base/pages/page-42/append", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: "text" }),
      });

      expect(res.status).toBe(502);
    });
  });

  describe("POST /pages", () => {
    it("creates a new page via core", async () => {
      vi.spyOn(coreClient, "knowledgeBaseCreatePage").mockResolvedValue({
        id: "page-new",
        title: "Fresh Page",
      } as any);

      const res = await makeApp().request("/api/knowledge-base/pages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "Fresh Page", content: "Initial content" }),
      });

      expect(res.status).toBe(201);
      const body = await res.json();
      expect(body.id).toBe("page-new");
      expect(coreClient.knowledgeBaseCreatePage).toHaveBeenCalledWith({
        title: "Fresh Page",
        content: "Initial content",
      });
    });

    it("returns 502 when core is unreachable during create", async () => {
      vi.spyOn(coreClient, "knowledgeBaseCreatePage").mockRejectedValue(new Error("ECONNREFUSED"));

      const res = await makeApp().request("/api/knowledge-base/pages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "Test" }),
      });

      expect(res.status).toBe(502);
    });
  });
});
