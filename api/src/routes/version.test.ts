import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { version } from "./version.js";

function makeApp() {
  const app = new Hono();
  app.route("/v1/version", version);
  return app;
}

describe("version route", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns API version and features when core is reachable", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          version: "v1",
          api_version: "0.1.0",
          service: "mascarade-core",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    const res = await makeApp().request("/v1/version");

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data).toMatchObject({
      api_version: "0.1.0",
      service: "mascarade-api",
      core: {
        version: "v1",
        api_version: "0.1.0",
        service: "mascarade-core",
      },
      supported_features: [
        "versioned_endpoints",
        "deprecation_headers",
        "openai_compatibility",
      ],
    });
    expect(fetchSpy).toHaveBeenCalledWith(expect.stringContaining("/v1/version"));
  });

  it("returns degraded status when core is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Connection refused"));

    const res = await makeApp().request("/v1/version");

    expect(res.status).toBe(503);
    const data = await res.json();
    expect(data).toMatchObject({
      api_version: "0.1.0",
      service: "mascarade-api",
      core: "unreachable",
      supported_features: [
        "versioned_endpoints",
        "deprecation_headers",
        "openai_compatibility",
      ],
    });
  });

  it("handles non-ok response from core", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("Service Unavailable", {
        status: 503,
      }),
    );

    const res = await makeApp().request("/v1/version");

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data).toMatchObject({
      api_version: "0.1.0",
      service: "mascarade-api",
      core: "unreachable",
    });
  });
});
