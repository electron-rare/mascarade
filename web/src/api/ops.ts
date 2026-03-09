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
  observability: {
    traces_backend: "tempo";
    logs_backend: "loki";
    metrics_backend: "prometheus";
    tempo: {
      name: string;
      url: string;
      ok: boolean;
      status: number;
      latency_ms: number;
      error?: string;
    } | null;
    grafana_proxy_url: string;
    langfuse_proxy_url: string;
  };
  public: {
    proxy_enabled: boolean;
    bind_host: string;
    public_bind: boolean;
    server_name: string;
    auth_configured: boolean;
    surfaces: Array<{
      name: string;
      host: string;
      url: string;
      protected: boolean;
      ok: boolean;
      status: number;
      latency_ms: number;
      note: string;
      error?: string;
    }>;
  };
  industrial?: {
    ui: {
      host: string;
      url: string;
      ok: boolean;
      status: number;
      latency_ms: number;
      note: string;
      error?: string;
    } | null;
    summary: {
      server_count: number;
      runtime_ok_count: number;
      runtime_error_count: number;
      topology_valid: boolean;
      vendor_contract_ready_count: number;
      vendor_contract_blocked_count: number;
      cockpit_service_ok: boolean;
      cockpit_proxy_ok: boolean;
    };
    servers: Array<{
      key: string;
      label: string;
      description: string;
      ok: boolean;
      runtime_ok: boolean;
      protocol_version?: string;
      tool_count: number;
      resource_count: number;
      prompt_count: number;
      error?: string;
      health?: {
        system?: string;
        health?: {
          configured?: boolean;
          auth_mode?: string;
          auth_configured?: boolean;
          contract_ready?: boolean;
          contract_status?: string;
          operation_statuses?: Array<{
            operation: string;
            mode?: string;
            configured?: boolean;
            contract_ready?: boolean;
            resource_configured?: boolean;
            warnings?: string[];
          }>;
          ready_operation_count?: number;
          simulated_operation_count?: number;
          blocked_operation_count?: number;
          warnings?: string[];
        };
      };
      contract?: {
        domain?: string;
        status?: string;
        pack_id?: string;
        blockers?: string[];
        auth_modes?: string[];
        operations?: string[];
        operation_items?: Array<{
          operation: string;
          status?: string;
          method?: string;
          live_ready?: boolean;
          blockers?: string[];
        }>;
      };
    }>;
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

export type OpsMcpServerStatus = {
  ok: boolean;
  status: string;
  requested_runtime?: string | null;
  runtime_mode?: string | null;
  protocol_version?: string | null;
  server_name?: string | null;
  tool_count: number;
  resource_count: number;
  prompt_count: number;
  latency_ms?: number | null;
  checks?: string[];
  secret_configured?: boolean | null;
  token_configured?: boolean | null;
  live_requested?: boolean | null;
  live_validation?: string | null;
  error?: string | null;
};

export type OpsMcpSummary = OpsMcpServerStatus & {
  aggregate_status?: string;
  primary_server?: string;
  primary?: OpsMcpServerStatus | null;
  server_count?: number;
  servers_ok?: number;
  degraded_servers?: string[];
  servers?: Record<string, OpsMcpServerStatus>;
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
    gpu?: boolean;
    loki_history: boolean;
    tempo_traces?: boolean;
    otel: boolean;
    agentsight: boolean;
  };
  observability?: OpsMonitor["observability"];
  public?: OpsMonitor["public"];
  industrial?: OpsMonitor["industrial"];
  gpu?: OpsSourceStatus | null;
  cluster?: {
    enabled: boolean;
    node_id?: string | null;
    role?: string | null;
    peers_total: number;
    peers_ok: number;
  };
  mcp?: OpsMcpSummary | null;
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
    routing_role?: string;
    routing_provider?: string;
    routing_model?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.limit) search.set("limit", String(params.limit));
    if (params?.source) search.set("source", params.source);
    if (params?.severity) search.set("severity", params.severity);
    if (params?.run_id) search.set("run_id", params.run_id);
    if (params?.agent_name) search.set("agent_name", params.agent_name);
    if (params?.event_type) search.set("event_type", params.event_type);
    if (params?.service) search.set("service", params.service);
    if (params?.routing_role) search.set("routing_role", params.routing_role);
    if (params?.routing_provider) search.set("routing_provider", params.routing_provider);
    if (params?.routing_model) search.set("routing_model", params.routing_model);
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
    routing_role?: string;
    routing_provider?: string;
    routing_model?: string;
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
    if (params?.routing_role) search.set("routing_role", params.routing_role);
    if (params?.routing_provider) search.set("routing_provider", params.routing_provider);
    if (params?.routing_model) search.set("routing_model", params.routing_model);
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
      String(source === "docker-event"),
    );
    search.set("backfill", source === "docker-event" ? "20" : "12");
    search.set("live_limit", source === "docker-event" ? "24" : "18");
    search.set("poll_interval_ms", "1500");

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
