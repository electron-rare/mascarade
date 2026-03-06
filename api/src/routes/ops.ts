import { Hono } from "hono";
import {
  coreClient,
  getCoreAuthHeaders,
  type AgentTraceEvent,
} from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

type ProbeResult = {
  name: string;
  url: string;
  ok: boolean;
  status: number;
  latency_ms: number;
  error?: string;
};

type TimedJsonResult = {
  ok: boolean;
  status: number;
  latencyMs: number;
  json?: any;
  error?: string;
};

type OpsLogEntry = {
  id: string;
  ts: string;
  source: "service" | "agent-trace";
  service?: string;
  severity: "debug" | "info" | "warning" | "error" | "critical";
  message: string;
  run_id?: string;
  agent_name?: string | null;
  from_agent?: string | null;
  to_agent?: string | null;
  event_type?: string;
  labels?: Record<string, string>;
};

type MonitorSnapshot = {
  timestamp: string;
  gateway: {
    api: { ok: boolean; status: number };
    core: boolean;
  };
  ai: {
    ollama: {
      ok: boolean;
      status: number;
      latency_ms: number;
      models: number;
      error?: string;
    };
    apple_llm: null | {
      ok: boolean;
      status: number;
      latency_ms: number;
      backend: string | null;
      model_id: string | null;
      runtime_ready: boolean | null;
      error?: string | null;
    };
    qdrant: {
      ok: boolean;
      status: number;
      latency_ms: number;
      collections: number;
      error?: string;
    };
  };
  services: ProbeResult[];
  core_metrics: {
    ok: boolean;
    status: number;
    data: Record<string, unknown> | null;
    error?: string;
  };
};

async function timedJson(
  url: string,
  timeoutMs: number = 1800,
  headers?: Record<string, string>,
): Promise<TimedJsonResult> {
  const started = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { headers, signal: controller.signal });
    const latencyMs = Date.now() - started;
    const json = await res.json().catch(() => undefined);
    return { ok: res.ok, status: res.status, latencyMs, json };
  } catch (error) {
    const latencyMs = Date.now() - started;
    return {
      ok: false,
      status: 0,
      latencyMs,
      error: error instanceof Error ? error.message : "network error",
    };
  } finally {
    clearTimeout(timer);
  }
}

async function timedProbe(
  name: string,
  url: string,
  timeoutMs: number = 1500,
): Promise<ProbeResult> {
  const started = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    return {
      name,
      url,
      ok: res.ok,
      status: res.status,
      latency_ms: Date.now() - started,
    };
  } catch (error) {
    return {
      name,
      url,
      ok: false,
      status: 0,
      latency_ms: Date.now() - started,
      error: error instanceof Error ? error.message : "network error",
    };
  } finally {
    clearTimeout(timer);
  }
}

const OLLAMA_BASE_URL = (process.env.OLLAMA_BASE_URL || "http://ollama:11434").replace(/\/+$/, "");
const APPLE_LLM_ENABLED = (process.env.APPLE_LLM_ENABLED || "").toLowerCase() === "true";
const APPLE_LLM_BASE_URL = (process.env.APPLE_LLM_BASE_URL || "").replace(/\/+$/, "");

function severityRank(severity: OpsLogEntry["severity"]): number {
  switch (severity) {
    case "debug":
      return 10;
    case "info":
      return 20;
    case "warning":
      return 30;
    case "error":
      return 40;
    case "critical":
      return 50;
    default:
      return 20;
  }
}

function coerceSeverity(value: string | undefined): OpsLogEntry["severity"] | null {
  if (!value) return null;
  const normalized = value.trim().toLowerCase();
  if (
    normalized === "debug" ||
    normalized === "info" ||
    normalized === "warning" ||
    normalized === "error" ||
    normalized === "critical"
  ) {
    return normalized;
  }
  return null;
}

function traceToLogEntry(event: AgentTraceEvent): OpsLogEntry {
  return {
    id: event.id,
    ts: event.ts,
    source: "agent-trace",
    severity: event.severity,
    message: event.message,
    run_id: event.run_id,
    agent_name: event.agent_name,
    from_agent: event.from_agent,
    to_agent: event.to_agent,
    event_type: event.event_type,
    labels: {
      mode: event.mode,
      provider: event.provider ?? "",
      model: event.model ?? "",
    },
  };
}

function probeToLogEntry(probe: ProbeResult, timestamp: string): OpsLogEntry | null {
  if (probe.ok) {
    return null;
  }

  const severity: OpsLogEntry["severity"] =
    probe.status >= 500 || probe.status === 0 ? "error" : "warning";

  return {
    id: `${probe.name}:${timestamp}`,
    ts: timestamp,
    source: "service",
    service: probe.name,
    severity,
    message: probe.error
      ? `${probe.name} probe failed: ${probe.error}`
      : `${probe.name} returned HTTP ${probe.status}`,
    labels: {
      url: probe.url,
      status: String(probe.status),
      latency_ms: String(probe.latency_ms),
    },
  };
}

function sortLogs(entries: OpsLogEntry[]): OpsLogEntry[] {
  return [...entries].sort((left, right) => {
    const tsDiff = new Date(right.ts).getTime() - new Date(left.ts).getTime();
    if (tsDiff !== 0) return tsDiff;
    return severityRank(right.severity) - severityRank(left.severity);
  });
}

async function collectMonitorSnapshot(): Promise<MonitorSnapshot> {
  const probes = await Promise.all([
    timedProbe("core", "http://core:8100/health"),
    timedProbe("openwebui", "http://open-webui:8080/"),
    timedProbe("grafana", "http://grafana:3000/api/health"),
    timedProbe("n8n", "http://n8n:5678/"),
    timedProbe("langfuse", "http://langfuse-web:3000/"),
    timedProbe("dify-web", "http://dify-web:3000/"),
    timedProbe("dify-api", "http://dify-api:5001/health"),
  ]);

  const [ollama, qdrant, coreMetrics] = await Promise.all([
    timedJson(`${OLLAMA_BASE_URL}/api/tags`, 2200),
    timedJson("http://qdrant:6333/collections", 2200),
    timedJson("http://core:8100/metrics", 2200, getCoreAuthHeaders()),
  ]);
  const appleLLM = APPLE_LLM_ENABLED && APPLE_LLM_BASE_URL
    ? await timedJson(`${APPLE_LLM_BASE_URL}/health`, 2200)
    : null;

  const ollamaModels = Array.isArray(ollama.json?.models) ? ollama.json.models.length : 0;
  const qdrantCollections = Array.isArray(qdrant.json?.result?.collections)
    ? qdrant.json.result.collections.length
    : 0;

  return {
    timestamp: new Date().toISOString(),
    gateway: {
      api: { ok: true, status: 200 },
      core: probes.find((p) => p.name === "core")?.ok ?? false,
    },
    ai: {
      ollama: {
        ok: ollama.ok,
        status: ollama.status,
        latency_ms: ollama.latencyMs,
        models: ollamaModels,
        error: ollama.error,
      },
      apple_llm: appleLLM ? {
        ok: appleLLM.ok,
        status: appleLLM.status,
        latency_ms: appleLLM.latencyMs,
        backend: appleLLM.json?.backend ?? null,
        model_id: appleLLM.json?.model_id ?? null,
        runtime_ready: appleLLM.json?.runtime_ready ?? null,
        error: appleLLM.error ?? appleLLM.json?.runtime_error,
      } : null,
      qdrant: {
        ok: qdrant.ok,
        status: qdrant.status,
        latency_ms: qdrant.latencyMs,
        collections: qdrantCollections,
        error: qdrant.error,
      },
    },
    services: probes,
    core_metrics: {
      ok: coreMetrics.ok,
      status: coreMetrics.status,
      data: coreMetrics.json ?? null,
      error: coreMetrics.error,
    },
  };
}

function getNumberParam(value: string | undefined, fallback: number, max: number): number {
  const parsed = Number.parseInt(value || "", 10);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return Math.min(parsed, max);
}

const ops = new Hono();

ops.get("/monitor", async (c) => c.json(await collectMonitorSnapshot()));

ops.get("/sources", async (c) =>
  c.json({
    service_monitor: { available: true, kind: "http-probe" },
    agent_traces: { available: true, kind: "native-trace" },
    machine_logs: { available: false, kind: "pending-ops-agent" },
    docker_events: { available: false, kind: "pending-ops-agent" },
    loki_history: { available: false, kind: "pending-loki" },
    otel: { available: false, kind: "pending-otel" },
    agentsight: { available: false, kind: "optional-complement" },
  }),
);

ops.get("/summary", async (c) => {
  try {
    const [monitor, traces] = await Promise.all([
      collectMonitorSnapshot(),
      coreClient.recentAgentTraces({ limit: 60 }),
    ]);

    const recentRuns = Array.from(
      new Map(
        traces.events
          .filter((event) => event.run_id)
          .map((event) => [event.run_id, event]),
      ).values(),
    ).slice(-10).reverse();

    const activeRuns = new Set(
      traces.events
        .filter((event) => event.event_type === "run_started")
        .map((event) => event.run_id),
    );
    for (const event of traces.events) {
      if (event.event_type === "run_completed" || event.event_type === "run_failed") {
        activeRuns.delete(event.run_id);
      }
    }

    return c.json({
      timestamp: monitor.timestamp,
      monitor,
      traces: {
        total_recent: traces.count,
        active_runs: activeRuns.size,
        recent_runs: recentRuns.map((event) => ({
          run_id: event.run_id,
          mode: event.mode,
          agent_name: event.agent_name,
          event_type: event.event_type,
          ts: event.ts,
          message: event.message,
        })),
      },
      alerts: sortLogs([
        ...traces.events
          .filter((event) => event.severity === "error" || event.severity === "critical")
          .map(traceToLogEntry),
        ...monitor.services
          .map((probe) => probeToLogEntry(probe, monitor.timestamp))
          .filter((entry): entry is OpsLogEntry => entry !== null),
      ]).slice(0, 25),
      sources: {
        service_monitor: true,
        agent_traces: true,
        machine_logs: false,
        docker_events: false,
        loki_history: false,
        otel: false,
        agentsight: false,
      },
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

ops.get("/agent-traces/recent", async (c) => {
  try {
    const query = c.req.query();
    const result = await coreClient.recentAgentTraces({
      limit: getNumberParam(query.limit, 50, 500),
      run_id: query.run_id,
      agent_name: query.agent_name,
      event_type: query.event_type,
    });
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

ops.get("/agent-traces/:runId", async (c) => {
  try {
    const runId = c.req.param("runId");
    const limit = getNumberParam(c.req.query("limit"), 200, 1000);
    const result = await coreClient.runAgentTraces(runId, limit);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

ops.get("/logs/recent", async (c) => {
  try {
    const query = c.req.query();
    const source = query.source || "all";
    const minSeverity = coerceSeverity(query.severity) || "info";
    const limit = getNumberParam(query.limit, 80, 400);

    const [monitor, traces] = await Promise.all([
      collectMonitorSnapshot(),
      coreClient.recentAgentTraces({
        limit,
        run_id: query.run_id,
        agent_name: query.agent_name,
        event_type: query.event_type,
      }),
    ]);

    const entries: OpsLogEntry[] = [];

    if (source === "all" || source === "agent-trace") {
      entries.push(...traces.events.map(traceToLogEntry));
    }
    if (source === "all" || source === "service") {
      entries.push(
        ...monitor.services
          .map((probe) => probeToLogEntry(probe, monitor.timestamp))
          .filter((entry): entry is OpsLogEntry => entry !== null),
      );
      if (!monitor.core_metrics.ok) {
        entries.push({
          id: `core-metrics:${monitor.timestamp}`,
          ts: monitor.timestamp,
          source: "service",
          service: "core-metrics",
          severity: "warning",
          message: monitor.core_metrics.error
            ? `core metrics unavailable: ${monitor.core_metrics.error}`
            : `core metrics unavailable (${monitor.core_metrics.status})`,
        });
      }
    }

    const filtered = sortLogs(entries)
      .filter((entry) => severityRank(entry.severity) >= severityRank(minSeverity))
      .slice(0, limit);

    return c.json({
      entries: filtered,
      count: filtered.length,
      timestamp: monitor.timestamp,
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { ops };
