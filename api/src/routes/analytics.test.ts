import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { analytics } from "./analytics.js";

const ORIGINAL_FETCH = global.fetch;

function makeApp() {
  const app = new Hono();
  app.route("/api/analytics", analytics);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
  if (ORIGINAL_FETCH === undefined) {
    // @ts-expect-error test cleanup for environments without fetch
    delete global.fetch;
  } else {
    global.fetch = ORIGINAL_FETCH;
  }
});

describe("analytics benchmarks endpoint", () => {
  it("proxies benchmark data from core analytics service", async () => {
    const mockBenchmarks = {
      benchmarks: [
        {
          id: "bench-1",
          model: "gpt-4",
          task: "code_generation",
          score: 0.92,
          timestamp: "2026-03-14T10:00:00Z",
        },
        {
          id: "bench-2",
          model: "claude-3-opus",
          task: "code_generation",
          score: 0.95,
          timestamp: "2026-03-14T10:00:00Z",
        },
      ],
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mockBenchmarks), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/analytics/v1/benchmarks", {
      method: "GET",
    });

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8100/v1/analytics/benchmarks");
    expect(await res.json()).toEqual(mockBenchmarks);
  });

  it("returns 502 when core returns not found", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "No benchmarks found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/analytics/v1/benchmarks", {
      method: "GET",
    });

    expect(res.status).toBe(502);
    const json = await res.json();
    expect(json).toEqual({ error: "Core service unreachable" });
  });

  it("returns 502 when core service fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Internal server error" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/analytics/v1/benchmarks", {
      method: "GET",
    });

    expect(res.status).toBe(502);
    const json = await res.json();
    expect(json).toEqual({ error: "Core service unreachable" });
  });

  it("handles network errors gracefully", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("Network error"));
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/analytics/v1/benchmarks", {
      method: "GET",
    });

    expect(res.status).toBe(502);
    const json = await res.json();
    expect(json).toEqual({ error: "Core service unreachable" });
  });

  it("handles timeout errors", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("The operation was aborted"));
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/analytics/v1/benchmarks", {
      method: "GET",
    });

    expect(res.status).toBe(502);
    const json = await res.json();
    expect(json).toEqual({ error: "Core service unreachable" });
  });

  it("handles non-json error responses from core", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("Bad Gateway", {
        status: 502,
        headers: { "Content-Type": "text/plain" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await makeApp().request("/api/analytics/v1/benchmarks", {
      method: "GET",
    });

    expect(res.status).toBe(502);
    const json = await res.json();
    expect(json).toEqual({ error: "Core service unreachable" });
  });

  it("includes auth headers when proxying to core", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ benchmarks: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await makeApp().request("/api/analytics/v1/benchmarks", {
      method: "GET",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const fetchCall = fetchMock.mock.calls[0];
    expect(fetchCall?.[1]?.headers).toMatchObject({
      "Content-Type": "application/json",
    });
  });
});
