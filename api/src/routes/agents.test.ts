import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { agents } from "./agents.js";

const ORIGINAL_FETCH = global.fetch;

function makeApp() {
  const app = new Hono();
  app.route("/v1/api/agents", agents);
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

describe("agents provider mutations", () => {
  it("proxies provider saves through ops-agent and rehydrates provider status", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          updated_env: ["OLLAMA_ENABLED"],
          restarted_services: ["core"],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(coreClient, "providersStatus").mockResolvedValue({
      providers: [{ name: "ollama", active: true, configured: true }] as any,
    });

    const res = await makeApp().request("/v1/api/agents/providers/ollama/key", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keys: { OLLAMA_ENABLED: "true" } }),
    });

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://ops-agent:9200/providers/ollama");
    expect(await res.json()).toEqual({
      status: "ok",
      active: true,
      configured: true,
      updated_env: ["OLLAMA_ENABLED"],
      restarted_services: ["core"],
    });
  });

  it("proxies provider clears through ops-agent and returns the refreshed state", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          message: "Provider settings cleared",
          cleared_env: ["OLLAMA_BASE_URL", "OLLAMA_ENABLED"],
          restarted_services: ["core"],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(coreClient, "providersStatus").mockResolvedValue({
      providers: [{ name: "ollama", active: false, configured: false }] as any,
    });

    const res = await makeApp().request("/v1/api/agents/providers/ollama/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    expect(res.status).toBe(200);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://ops-agent:9200/providers/ollama/clear");
    expect(await res.json()).toEqual({
      status: "ok",
      active: false,
      configured: false,
      message: "Provider settings cleared",
      cleared_env: ["OLLAMA_BASE_URL", "OLLAMA_ENABLED"],
      restarted_services: ["core"],
    });
  });

  it("passes field-scoped provider clears through to ops-agent", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          message: "Provider settings cleared",
          cleared_env: ["OLLAMA_BASE_URL"],
          restarted_services: ["core"],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(coreClient, "providersStatus").mockResolvedValue({
      providers: [{ name: "ollama", active: true, configured: true }] as any,
    });

    const res = await makeApp().request("/v1/api/agents/providers/ollama/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields: ["OLLAMA_BASE_URL"] }),
    });

    expect(res.status).toBe(200);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://ops-agent:9200/providers/ollama/clear");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ fields: ["OLLAMA_BASE_URL"] }),
    });
    expect(await res.json()).toEqual({
      status: "ok",
      active: true,
      configured: true,
      message: "Provider settings cleared",
      cleared_env: ["OLLAMA_BASE_URL"],
      restarted_services: ["core"],
    });
  });
});
