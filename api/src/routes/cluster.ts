import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";
import { validate } from "../validation/index.js";
import { ClusterForwardSendRequestSchema } from "../validation/schemas.js";

const cluster = new Hono();

function asWorkerNode(
  workerId: string,
  worker: Record<string, unknown>,
  peerMap: Map<string, { role?: string; base_url?: string }>,
) {
  const peer = peerMap.get(workerId);
  return {
    node_id: String(worker.node_id || workerId),
    role: String(worker.role || peer?.role || "worker"),
    state: String(worker.status || "unknown"),
    queue_depth: Number(worker.queue_depth || 0),
    cpu_util: Number(worker.cpu_percent || 0),
    gpu_util: Number(worker.gpu_percent || 0),
    ram_free_mb: Number(worker.ram_free_mb || 0),
    vram_free_mb: Number(worker.vram_free_mb || 0),
    runtime_status: String(worker.runtime || "unknown"),
    recent_failure_rate: Number(worker.error_rate || 0),
    base_url: peer?.base_url || null,
  };
}

cluster.get("/identity", async (c) => {
  try {
    const result = await coreClient.clusterIdentity();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cluster.get("/peers", async (c) => {
  try {
    const result = await coreClient.clusterPeers();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cluster.get("/state", async (c) => {
  try {
    const [{ node, peers }, scheduler] = await Promise.all([
      coreClient.clusterPeers(),
      coreClient.schedulerStatus().catch(() => ({
        enabled: false,
        workers: {},
        total_queue_depth: 0,
        total_dispatched: 0,
        alive_workers: 0,
        dead_workers: 0,
      })),
    ]);

    const peerMap = new Map(peers.map((peer) => [peer.remote_node_id || peer.peer_id, peer]));
    const schedulerWorkers = Object.entries(scheduler.workers || {}).map(([workerId, worker]) =>
      asWorkerNode(workerId, worker as Record<string, unknown>, peerMap),
    );
    const nodes =
      schedulerWorkers.length > 0
        ? schedulerWorkers
        : [
            {
              node_id: node.node_id,
              role: node.role,
              state: "ready",
              queue_depth: 0,
              cpu_util: 0,
              gpu_util: 0,
              ram_free_mb: 0,
              vram_free_mb: 0,
              runtime_status: "core",
              recent_failure_rate: 0,
              base_url: node.base_url,
            },
            ...peers.map((peer) => ({
              node_id: peer.remote_node_id || peer.peer_id,
              role: peer.role,
              state: peer.ok ? "ready" : "unreachable",
              queue_depth: 0,
              cpu_util: 0,
              gpu_util: 0,
              ram_free_mb: 0,
              vram_free_mb: 0,
              runtime_status: peer.ok ? "peer" : "error",
              recent_failure_rate: peer.ok ? 0 : 1,
              base_url: peer.base_url,
            })),
          ];

    return c.json({
      nodes,
      scheduler: {
        enabled: scheduler.enabled,
        global_queue_bytes: 0,
        total_queue_depth: scheduler.total_queue_depth || 0,
        total_dispatched: scheduler.total_dispatched || 0,
        leases: [],
      },
      backpressure: {
        global_queue_items: scheduler.total_queue_depth || 0,
        global_queue_bytes: 0,
        is_under_pressure: (scheduler.total_queue_depth || 0) > 100,
        load_factor: Math.min((scheduler.total_queue_depth || 0) / 200, 1),
      },
      capacity: {
        cluster: "mascarade-cluster",
        alive_workers: scheduler.alive_workers || 0,
        dead_workers: scheduler.dead_workers || 0,
      },
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cluster.get("/events", async (c) => {
  try {
    const rawLimit = c.req.query("limit");
    const limit = rawLimit ? Number.parseInt(rawLimit, 10) : 20;
    const traces = await coreClient.recentAgentTraces({
      limit: Number.isFinite(limit) ? limit : 20,
    });

    return c.json({
      events: traces.events.map((event) => ({
        ts: event.ts,
        level: event.severity,
        event_type: event.event_type,
        data: {
          project_id: null,
          node_id: event.routing_provider || null,
          request_id: event.run_id || null,
          lease_id: null,
          agent_name: event.agent_name || null,
          provider: event.provider || null,
          model: event.model || null,
        },
        message: event.message,
      })),
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

cluster.post("/forward/send", validate(ClusterForwardSendRequestSchema), async (c) => {
  try {
    const body = c.get("validated" as never);
    const result = await coreClient.clusterForwardSend(body as any);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { cluster };
