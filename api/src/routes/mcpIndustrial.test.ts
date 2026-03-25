import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { industrialMcp } from "./mcpIndustrial.js";

function makeApp() {
  const app = new Hono();
  app.route("/v1/api/mcp/industrial", industrialMcp);
  return app;
}

describe("industrial MCP HTTP proxy routes", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("proxies suite metadata to the cockpit MCP HTTP suite", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true, server_count: 7 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const res = await makeApp().request("/v1/api/mcp/industrial", {
      headers: {
        "Cf-Access-Authenticated-User-Email": "c.saillant@gmail.com",
      },
    });

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, server_count: 7 });
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://agent-factory-cockpit:4173/mcp/industrial",
      expect.objectContaining({
        method: "GET",
        headers: expect.any(Headers),
      }),
    );
    const forwarded = fetchSpy.mock.calls[0]?.[1] as RequestInit;
    const headers = forwarded.headers as Headers;
    expect(headers.get("X-Forwarded-User")).toBe("c.saillant@gmail.com");
    expect(headers.get("X-Forwarded-Email")).toBe("c.saillant@gmail.com");
    expect(headers.get("X-Forwarded-Groups")).toContain("operator");
  });

  it("proxies JSON-RPC POST calls to one industrial MCP server using trusted identity headers only", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ jsonrpc: "2.0", id: 1, result: { tools: [] } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const rpcBody = {
      jsonrpc: "2.0",
      id: 1,
      method: "tools/list",
      params: {},
    };
    const res = await makeApp().request("/v1/api/mcp/industrial/cockpit-ops", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Forwarded-User": "spoofed-user",
        "X-Forwarded-Email": "spoofed@example.com",
        "X-Forwarded-Groups": "admin",
        "X-Auth-Request-User": "ops",
        "X-Auth-Request-Email": "ops@example.com",
        "X-Auth-Request-Groups": "operator,approver",
      },
      body: JSON.stringify(rpcBody),
    });

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ jsonrpc: "2.0", id: 1, result: { tools: [] } });
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://agent-factory-cockpit:4173/mcp/industrial/cockpit-ops",
      expect.objectContaining({
        method: "POST",
        headers: expect.any(Headers),
        body: JSON.stringify(rpcBody),
      }),
    );
    const forwarded = fetchSpy.mock.calls[0]?.[1] as RequestInit;
    const headers = forwarded.headers as Headers;
    expect(headers.get("X-Forwarded-User")).toBe("ops");
    expect(headers.get("X-Forwarded-Email")).toBe("ops@example.com");
    expect(headers.get("X-Forwarded-Groups")).toBe("operator,approver");
  });
});
