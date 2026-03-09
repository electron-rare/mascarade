import { Hono } from "hono";
import { describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { industrial } from "./industrial.js";

function makeApp() {
  const app = new Hono();
  app.route("/api/industrial", industrial);
  return app;
}

describe("industrial routes", () => {
  it("proxies industrial platform discovery to the core facade", async () => {
    vi.spyOn(coreClient, "industrialMcpPlatform").mockResolvedValue({
      summary: {
        server_count: 7,
        runtime_ok_count: 7,
        runtime_error_count: 0,
        topology_valid: true,
        vendor_contract_ready_count: 4,
        vendor_contract_blocked_count: 2,
      },
      servers: [
        {
          key: "cockpit-ops",
          label: "Industrial Cockpit Ops",
          description: "Operator control plane",
          ok: true,
          runtime_ok: true,
          tool_count: 12,
          resource_count: 10,
          prompt_count: 2,
        },
      ],
      topology: { valid: true },
      vendor_contracts: { summary: { ready_count: 4, blocked_count: 2 } },
    } as any);

    const res = await makeApp().request("/api/industrial/platform");

    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({
      summary: {
        server_count: 7,
        runtime_ok_count: 7,
      },
      servers: [
        {
          key: "cockpit-ops",
          label: "Industrial Cockpit Ops",
        },
      ],
    });
  });

  it("proxies industrial tool calls to the core facade", async () => {
    vi.spyOn(coreClient, "industrialMcpTool").mockResolvedValue({
      ok: true,
      run_id: "run-industrial-001",
      server_key: "plm",
      tool_name: "spec_sync",
      message: "executed",
      payload: {
        result: {
          system: "plm",
        },
      },
    } as any);

    const res = await makeApp().request("/api/industrial/plm/tools/spec_sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        arguments: {
          record_id: "PLM-001",
        },
        run_id: "run-industrial-001",
      }),
    });

    expect(res.status).toBe(200);
    expect(coreClient.industrialMcpTool).toHaveBeenCalledWith("plm", "spec_sync", {
      arguments: {
        record_id: "PLM-001",
      },
      run_id: "run-industrial-001",
    });
    expect(await res.json()).toEqual({
      ok: true,
      run_id: "run-industrial-001",
      server_key: "plm",
      tool_name: "spec_sync",
      message: "executed",
      payload: {
        result: {
          system: "plm",
        },
      },
    });
  });
});
