import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { settings } from "./settings.js";

const ORIGINAL_FETCH = global.fetch;

function makeApp() {
  const app = new Hono();
  app.route("/api/settings", settings);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
  if (ORIGINAL_FETCH === undefined) {
    // @ts-expect-error test cleanup
    delete global.fetch;
  } else {
    global.fetch = ORIGINAL_FETCH;
  }
});

describe("settings routes", () => {
  it("GET /runtime-secrets proxies to ops-agent and returns sanitized data", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          groups: [
            { name: "auth", fields: { MASCARADE_API_KEY: "sk-secret123456" } },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/settings/runtime-secrets");

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.groups).toBeDefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("PUT /runtime-secrets/:groupName saves values through ops-agent", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ status: "ok", updated_env: ["MY_KEY"] }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/settings/runtime-secrets/mygroup", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values: { MY_KEY: "my-value" } }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
  });

  it("POST /runtime-secrets/:groupName/clear clears fields via ops-agent", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ status: "ok", cleared_env: ["MY_KEY"] }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/settings/runtime-secrets/mygroup/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields: ["MY_KEY"] }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
  });

  it("returns 503 when ops-agent is unreachable", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/settings/runtime-secrets");

    expect(res.status).toBe(503);
    const body = await res.json();
    expect(body.error).toBeDefined();
  });

  it("POST /runtime-secrets/:groupName/generate generates a secret", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ status: "ok", generated_value: "gen-secret-abc123xyz" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/settings/runtime-secrets/auth/generate", {
      method: "POST",
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
    // generated_value should NOT be in the response (it is stripped)
    expect(body.generated_value).toBeUndefined();
  });
});
