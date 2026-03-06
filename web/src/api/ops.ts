import { get } from "./client";

export type OpsMonitor = {
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
    qdrant: {
      ok: boolean;
      status: number;
      latency_ms: number;
      collections: number;
      error?: string;
    };
  };
  services: {
    name: string;
    url: string;
    ok: boolean;
    status: number;
    latency_ms: number;
    error?: string;
  }[];
  core_metrics: {
    ok: boolean;
    status: number;
    data: Record<string, unknown> | null;
    error?: string;
  };
};

export type OpsSourceStatus = {
  available: boolean;
  kind: string;
};

export type OpsTraceEvent = {
  id: string;
  ts: string;
  run_id: string;
  mode: string;
  event_type: string;
  step: number;
  severity: "debug" | "info" | "warning" | "error" | "critical";
  agent_name?: string | null;
  from_agent?: string | null;
  to_agent?: string | null;
  prompt_excerpt?: string | null;
  content_excerpt?: string | null;
  provider?: string | null;
  model?: string | null;
  token_usage?: { input_tokens?: number; output_tokens?: number } | null;
  error?: string | null;
  message: string;
};

export type OpsLogEntry = {
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

export type OpsSummary = {
  timestamp: string;
  monitor: OpsMonitor;
  traces: {
    total_recent: number;
    active_runs: number;
    recent_runs: {
      run_id: string;
      mode: string;
      agent_name?: string | null;
      event_type: string;
      ts: string;
      message: string;
    }[];
  };
  alerts: OpsLogEntry[];
  sources: {
    service_monitor: boolean;
    agent_traces: boolean;
    machine_logs: boolean;
    docker_events: boolean;
    loki_history: boolean;
    otel: boolean;
    agentsight: boolean;
  };
};

export const opsApi = {
  monitor: () => get<OpsMonitor>("/api/ops/monitor"),
  summary: () => get<OpsSummary>("/api/ops/summary"),
  sources: () =>
    get<Record<string, OpsSourceStatus>>("/api/ops/sources"),
  recentLogs: (params?: {
    limit?: number;
    source?: "all" | "service" | "agent-trace";
    severity?: "debug" | "info" | "warning" | "error" | "critical";
    run_id?: string;
    agent_name?: string;
    event_type?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.limit) search.set("limit", String(params.limit));
    if (params?.source) search.set("source", params.source);
    if (params?.severity) search.set("severity", params.severity);
    if (params?.run_id) search.set("run_id", params.run_id);
    if (params?.agent_name) search.set("agent_name", params.agent_name);
    if (params?.event_type) search.set("event_type", params.event_type);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return get<{ entries: OpsLogEntry[]; count: number; timestamp: string }>(
      `/api/ops/logs/recent${suffix}`,
    );
  },
  recentAgentTraces: (params?: {
    limit?: number;
    run_id?: string;
    agent_name?: string;
    event_type?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.limit) search.set("limit", String(params.limit));
    if (params?.run_id) search.set("run_id", params.run_id);
    if (params?.agent_name) search.set("agent_name", params.agent_name);
    if (params?.event_type) search.set("event_type", params.event_type);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return get<{ events: OpsTraceEvent[]; count: number }>(
      `/api/ops/agent-traces/recent${suffix}`,
    );
  },
  runAgentTraces: (runId: string, limit: number = 200) =>
    get<{ run_id: string; events: OpsTraceEvent[]; count: number }>(
      `/api/ops/agent-traces/${encodeURIComponent(runId)}?limit=${encodeURIComponent(String(limit))}`,
    ),
};
