import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import * as authModule from "../middleware/auth.js";
import { health } from "./health.js";

function makeApp() {
  const app = new Hono();
  app.route("/health", health);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("health route", () => {
  it("reports auth_required from the auth middleware source of truth", async () => {
    vi.spyOn(authModule, "isAuthConfigured").mockReturnValue(true);
    vi.spyOn(coreClient, "health").mockResolvedValue({
      status: "healthy",
      providers: ["openai"],
      agents: 18,
    });

    const res = await makeApp().request("/health");

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({
      status: "ok",
      auth_required: true,
      core: {
        status: "healthy",
        providers: ["openai"],
        agents: 18,
      },
    });
  });

  it("keeps auth_required visible when the core is degraded", async () => {
    vi.spyOn(authModule, "isAuthConfigured").mockReturnValue(true);
    vi.spyOn(coreClient, "health").mockRejectedValue(new Error("core down"));

    const res = await makeApp().request("/health");

    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({
      status: "degraded",
      auth_required: true,
      core: "unreachable",
    });
  });
});