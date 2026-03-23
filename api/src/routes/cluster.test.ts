import { Hono } from "hono";
import { afterEach, describe, expect, it, vi } from "vitest";
import { coreClient } from "../client/core.js";
import { cluster } from "./cluster.js";

function makeApp() {
  const app = new Hono();
  app.route("/api/cluster", cluster);
  return app;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("cluster routes", () => {
  it("builds a monitorable cluster state from peers and scheduler status", async () => {
    vi.spyOn(coreClient, "clusterPeers").mockResolvedValue({
      node: {
        node_id: "photon-machine",
        role: "control-plane",
        label: "Photon",
        base_url: "http://192.168.0.119:3000",
        providers: [],
        provider_models: {},
        agents: 12,
        cluster_enabled: true,
      },
      peers: [
        {
          peer_id: "peer-kxkm",
          remote_node_id: "kxkm",
          role: "gpu-primary",
          base_url: "http://kxkm-ai:8100",
          ok: true,
          status: 200,
          latency_ms: 12,
        },
      ],
    });
    vi.spyOn(coreClient, "schedulerStatus").mockResolvedValue({
      enabled: true,
      workers: {
        kxkm: {
          node_id: "kxkm",
          status: "alive",
          queue_depth: 4,
          cpu_percent: 31,
          gpu_percent: 84,
          ram_free_mb: 8192,
          vram_free_mb: 4096,
          runtime: "ollama",
          error_rate: 0.02,
        },
      },
      total_queue_depth: 4,
      total_dispatched: 128,
      alive_workers: 1,
      dead_workers: 0,
    });

    const res = await makeApp().request("/api/cluster/state");
    const payload = await res.json();

    expect(res.status).toBe(200);
    expect(payload.nodes).toEqual([
      {
        node_id: "kxkm",
        role: "gpu-primary",
        state: "alive",
        queue_depth: 4,
        cpu_util: 31,
        gpu_util: 84,
        ram_free_mb: 8192,
        vram_free_mb: 4096,
        runtime_status: "ollama",
        recent_failure_rate: 0.02,
        base_url: "http://kxkm-ai:8100",
      },
    ]);
    expect(payload.scheduler.total_queue_depth).toBe(4);
    expect(payload.backpressure.global_queue_items).toBe(4);
  });

  it("maps recent traces to cluster events", async () => {
    vi.spyOn(coreClient, "recentAgentTraces").mockResolvedValue({
      count: 1,
      events: [
        {
          id: "evt-1",
          ts: "2026-03-21T18:00:00Z",
          run_id: "run-1",
          mode: "internal",
          event_type: "mcp_call_completed",
          step: 0,
          severity: "info",
          message: "completed",
          routing_provider: "kxkm",
          provider: "ollama",
          model: "qwen3.5:9b",
        },
      ] as any,
    });

    const res = await makeApp().request("/api/cluster/events?limit=5");
    const payload = await res.json();

    expect(res.status).toBe(200);
    expect(payload.events).toEqual([
      {
        ts: "2026-03-21T18:00:00Z",
        level: "info",
        event_type: "mcp_call_completed",
        data: {
          project_id: null,
          node_id: "kxkm",
          request_id: "run-1",
          lease_id: null,
          agent_name: null,
          provider: "ollama",
          model: "qwen3.5:9b",
        },
        message: "completed",
      },
    ]);
  });
});
