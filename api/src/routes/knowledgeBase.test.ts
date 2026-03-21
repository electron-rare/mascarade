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
});
