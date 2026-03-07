import { get } from "./client";

export type OpsLogSource =
  | "all"
  | "service"
  | "machine"
  | "docker-event"
  | "agent-trace";

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
      model_names: string[];
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
  routing_role?: string | null;
  routing_provider?: string | null;
  routing_model?: string | null;
  token_usage?: { input_tokens?: number; output_tokens?: number } | null;
  error?: string | null;
  message: string;
};

export type OpsLogEntry = {
  id: string;
  ts: string;
  source: "service" | "machine" | "agent-trace" | "docker-event";
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
    docker_logs?: boolean;
    machine_logs: boolean;
    docker_events: boolean;
    loki_history: boolean;
    otel: boolean;
    agentsight: boolean;
  };
  cluster?: {
    enabled: boolean;
    node_id?: string | null;
    role?: string | null;
    peers_total: number;
    peers_ok: number;
  };
  ops_agent?: Record<string, unknown> | null;
};

export const opsApi = {
  monitor: () => get<OpsMonitor>("/api/ops/monitor"),
  summary: () => get<OpsSummary>("/api/ops/summary"),
  sources: () =>
    get<Record<string, OpsSourceStatus>>("/api/ops/sources"),
  recentLogs: (params?: {
    limit?: number;
    source?: OpsLogSource;
    severity?: "debug" | "info" | "warning" | "error" | "critical";
    run_id?: string;
    agent_name?: string;
    event_type?: string;
    service?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.limit) search.set("limit", String(params.limit));
    if (params?.source) search.set("source", params.source);
    if (params?.severity) search.set("severity", params.severity);
    if (params?.run_id) search.set("run_id", params.run_id);
    if (params?.agent_name) search.set("agent_name", params.agent_name);
    if (params?.event_type) search.set("event_type", params.event_type);
    if (params?.service) search.set("service", params.service);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return get<{ entries: OpsLogEntry[]; count: number; timestamp: string }>(
      `/api/ops/logs/recent${suffix}`,
    );
  },
  queryLogs: (params?: {
    limit?: number;
    source?: OpsLogSource;
    severity?: "debug" | "info" | "warning" | "error" | "critical";
    run_id?: string;
    agent_name?: string;
    event_type?: string;
    service?: string;
    q?: string;
    since?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.limit) search.set("limit", String(params.limit));
    if (params?.source) search.set("source", params.source);
    if (params?.severity) search.set("severity", params.severity);
    if (params?.run_id) search.set("run_id", params.run_id);
    if (params?.agent_name) search.set("agent_name", params.agent_name);
    if (params?.event_type) search.set("event_type", params.event_type);
    if (params?.service) search.set("service", params.service);
    if (params?.q) search.set("q", params.q);
    if (params?.since) search.set("since", params.since);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return get<{ entries: OpsLogEntry[]; count: number; timestamp: string; source: string }>(
      `/api/ops/logs/query${suffix}`,
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
  logStreamPath: (params?: {
    source?: OpsLogSource;
    severity?: "debug" | "info" | "warning" | "error" | "critical";
    service?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.severity) search.set("severity", params.severity);
    if (params?.service) search.set("services", params.service);

    const source = params?.source ?? "all";
    search.set(
      "include_services",
      String(source === "all" || source === "service"),
    );
    search.set(
      "include_machine",
      String(source === "all" || source === "machine"),
    );
    search.set(
      "include_events",
      String(source === "all" || source === "docker-event"),
    );

    return `/api/ops/logs/stream?${search.toString()}`;
  },
  agentTraceStreamPath: (params?: {
    run_id?: string;
    agent_name?: string;
    event_type?: string;
    limit?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.run_id) search.set("run_id", params.run_id);
    if (params?.agent_name) search.set("agent_name", params.agent_name);
    if (params?.event_type) search.set("event_type", params.event_type);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return `/api/ops/agent-traces/stream${suffix}`;
  },
};
