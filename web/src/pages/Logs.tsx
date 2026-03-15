import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { agentsApi } from "../api/agents";
import {
  type OpsLogEntry,
  type OpsMcpServerStatus,
  type OpsLogSource,
  type OpsSourceStatus,
  type OpsSummary,
  type OpsTraceEvent,
  opsApi,
} from "../api/ops";
import { useApi } from "../hooks/useApi";
import { useFetch } from "../hooks/useFetch";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  InlineNotice,
  Input,
  LoadingPanel,
  Select,
} from "../components/ui";

type LogsPayload = {
  entries: OpsLogEntry[];
  count: number;
  timestamp: string;
};

const severityOptions = [
  { value: "debug", label: "debug+" },
  { value: "info", label: "info+" },
  { value: "warning", label: "warning+" },
  { value: "error", label: "error+" },
  { value: "critical", label: "critical only" },
];

const sourceOptions = [
  { value: "all", label: "all sources" },
  { value: "agent-trace", label: "agent traces" },
  { value: "service", label: "service incidents" },
  { value: "machine", label: "machine logs" },
  { value: "docker-event", label: "docker events" },
];

const modeOptions = [
  { value: "live", label: "live" },
  { value: "history", label: "history" },
];

const historyWindowOptions = [
  { value: "15m", label: "last 15m" },
  { value: "1h", label: "last 1h" },
  { value: "6h", label: "last 6h" },
  { value: "24h", label: "last 24h" },
];

function formatStamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function severityClasses(severity: OpsLogEntry["severity"]): string {
  switch (severity) {
    case "debug":
      return "border-border/70 text-amber-100/44";
    case "info":
      return "border-[#264132] text-[#9bf6c2]";
    case "warning":
      return "border-[#6d5c1c] text-[#ffd166]";
    case "error":
      return "border-[#7a2436] text-[#ff7d93]";
    case "critical":
      return "border-[#9e1d2f] bg-[#26060d] text-[#ff4c6d]";
    default:
      return "border-border/70 text-amber-100/44";
  }
}

function sourceBadgeTone(source: OpsLogEntry["source"]): "accent" | "error" | "muted" {
  if (source === "agent-trace") return "accent";
  if (source === "docker-event") return "muted";
  if (source === "service") return "error";
  return "muted";
}

function traceTone(eventType: string | undefined): string {
  if (eventType === "run_failed") return "text-error";
  if (eventType === "handoff") return "text-[#82ffc1]";
  if (eventType === "run_completed") return "text-[#8cffb7]";
  return "text-accent";
}

function nonEmptyLabel(value: string | undefined): string | null {
  return value && value.trim() ? value.trim() : null;
}

function pickOptionValue<T extends string>(
  value: string | null,
  options: Array<{ value: T }>,
  fallback: T,
): T {
  return options.some((option) => option.value === value) ? (value as T) : fallback;
}

function normalizeFilter(value: string): string {
  return value.trim().toLowerCase();
}

function matchesRoutingLabels(
  labels: Record<string, string> | undefined,
  filters: {
    role: string;
    provider: string;
    model: string;
    policy?: string;
  },
): boolean {
  const role = normalizeFilter(filters.role);
  const provider = normalizeFilter(filters.provider);
  const model = normalizeFilter(filters.model);
  const policy = normalizeFilter(filters.policy ?? "");

  if (role && normalizeFilter(labels?.routing_role ?? "") !== role) {
    return false;
  }
  if (provider && normalizeFilter(labels?.routing_provider ?? "") !== provider) {
    return false;
  }
  if (model && normalizeFilter(labels?.routing_model ?? "") !== model) {
    return false;
  }
  if (policy && normalizeFilter(labels?.routing_policy ?? "") !== policy) {
    return false;
  }
  return true;
}

function matchesRoutingEntry(
  entry: OpsLogEntry,
  filters: {
    role: string;
    provider: string;
    model: string;
  },
): boolean {
  return matchesRoutingLabels(entry.labels, filters);
}

function matchesRoutingTraceEvent(
  event: OpsTraceEvent,
  filters: {
    role: string;
    provider: string;
    model: string;
  },
): boolean {
  return matchesRoutingLabels(
    {
      routing_role: event.routing_role ?? "",
      routing_provider: event.routing_provider ?? "",
      routing_model: event.routing_model ?? "",
    },
    filters,
  );
}

function sourceTone(available: boolean): "accent" | "error" {
  return available ? "accent" : "error";
}

function mcpTone(status?: string): "accent" | "warning" | "error" | "muted" {
  if (status === "ready") return "accent";
  if (status === "degraded") return "warning";
  if (status === "failed") return "error";
  return "muted";
}

function formatLatency(ms?: number | null): string {
  if (!Number.isFinite(ms) || !ms || ms <= 0) return "-";
  return `${Math.round(ms)} ms`;
}

function formatRoutingLatency(ms?: number | string | null): string | null {
  const value = typeof ms === "string" ? Number(ms) : ms;
  if (!Number.isFinite(value) || value === undefined || value === null || value < 0) return null;
  return `${Math.round(value)} ms`;
}

function formatMcpName(name?: string | null): string {
  if (!name) return "unknown";
  return name.replace(/[-_]/g, " ");
}

function summarizeMcpServer(server: OpsMcpServerStatus): string {
  const stats = `${server.tool_count} tools / ${server.resource_count} resources / ${server.prompt_count} prompts`;
  if (server.error) return `${stats} / ${server.error}`;
  if (server.checks && server.checks.length > 0) {
    return `${stats} / ${server.checks.join(" / ")}`;
  }
  return stats;
}

function severityRank(severity: OpsLogEntry["severity"]): number {
  if (severity === "debug") return 10;
  if (severity === "info") return 20;
  if (severity === "warning") return 30;
  if (severity === "error") return 40;
  if (severity === "critical") return 50;
  return 20;
}

function mergeLiveEntries(current: OpsLogEntry[], incoming: OpsLogEntry[], limit: number = 180): OpsLogEntry[] {
  const byId = new Map<string, OpsLogEntry>();
  for (const entry of current) {
    byId.set(entry.id, entry);
  }
  for (const entry of incoming) {
    byId.set(entry.id, entry);
  }
  return Array.from(byId.values())
    .sort((left, right) => new Date(right.ts).getTime() - new Date(left.ts).getTime())
    .slice(0, limit);
}

function parseEventPayload<T>(event: MessageEvent): T | null {
  try {
    return JSON.parse(event.data) as T;
  } catch {
    return null;
  }
}

export default function Logs() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [mode, setMode] = useState<"live" | "history">(
    () =>
      pickOptionValue<"live" | "history">(
        searchParams.get("mode"),
        modeOptions as Array<{ value: "live" | "history" }>,
        "live",
      ),
  );
  const [source, setSource] = useState<OpsLogSource>(
    () =>
      pickOptionValue<OpsLogSource>(
        searchParams.get("source"),
        sourceOptions as Array<{ value: OpsLogSource }>,
        "all",
      ),
  );
  const [severity, setSeverity] = useState<"debug" | "info" | "warning" | "error" | "critical">(
    () =>
      pickOptionValue<"debug" | "info" | "warning" | "error" | "critical">(
        searchParams.get("severity"),
        severityOptions as Array<{ value: "debug" | "info" | "warning" | "error" | "critical" }>,
        "info",
      ),
  );
  const [runIdFilter, setRunIdFilter] = useState(() => searchParams.get("run_id") ?? "");
  const [agentFilter, setAgentFilter] = useState(() => searchParams.get("agent_name") ?? "");
  const [eventTypeFilter, setEventTypeFilter] = useState(() => searchParams.get("event_type") ?? "");
  const [routingRoleFilter, setRoutingRoleFilter] = useState(() => searchParams.get("routing_role") ?? "");
  const [routingProviderFilter, setRoutingProviderFilter] = useState(() => searchParams.get("routing_provider") ?? "");
  const [routingModelFilter, setRoutingModelFilter] = useState(() => searchParams.get("routing_model") ?? "");
  const [routingPolicyFilter, setRoutingPolicyFilter] = useState(() => searchParams.get("routing_policy") ?? "");
  const [serviceFilter, setServiceFilter] = useState(() => searchParams.get("service") ?? "");
  const [queryText, setQueryText] = useState(() => searchParams.get("q") ?? "");
  const [historyWindow, setHistoryWindow] = useState(
    () =>
      pickOptionValue<string>(
        searchParams.get("since"),
        historyWindowOptions as Array<{ value: string }>,
        "1h",
      ),
  );
  const [paused, setPaused] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [liveEntries, setLiveEntries] = useState<OpsLogEntry[]>([]);
  const [liveStatus, setLiveStatus] = useState<"idle" | "connecting" | "live" | "paused">("idle");
  const [liveError, setLiveError] = useState<string | null>(null);
  const liveSeenIdsRef = useRef<Set<string>>(new Set());
  const routingFilters = useMemo(
    () => ({
      role: routingRoleFilter,
      provider: routingProviderFilter,
      model: routingModelFilter,
      policy: routingPolicyFilter,
    }),
    [routingModelFilter, routingPolicyFilter, routingProviderFilter, routingRoleFilter],
  );

  const liveLogsPath = useMemo(() => {
    const search = new URLSearchParams({
      limit: "120",
      source,
      severity,
    });
    if (runIdFilter.trim()) search.set("run_id", runIdFilter.trim());
    if (agentFilter.trim()) search.set("agent_name", agentFilter.trim());
    if (eventTypeFilter.trim()) search.set("event_type", eventTypeFilter.trim());
    if (routingRoleFilter.trim()) search.set("routing_role", routingRoleFilter.trim());
    if (routingProviderFilter.trim()) search.set("routing_provider", routingProviderFilter.trim());
    if (routingModelFilter.trim()) search.set("routing_model", routingModelFilter.trim());
    if (routingPolicyFilter.trim()) search.set("routing_policy", routingPolicyFilter.trim());
    if (serviceFilter.trim()) search.set("service", serviceFilter.trim());
    return `/api/ops/logs/recent?${search.toString()}`;
  }, [
    agentFilter,
    eventTypeFilter,
    routingModelFilter,
    routingProviderFilter,
    routingRoleFilter,
    routingPolicyFilter,
    runIdFilter,
    serviceFilter,
    severity,
    source,
  ]);

  const historyLogsPath = useMemo(() => {
    const search = new URLSearchParams({
      limit: "120",
      source,
      severity,
      since: historyWindow,
    });
    if (runIdFilter.trim()) search.set("run_id", runIdFilter.trim());
    if (agentFilter.trim()) search.set("agent_name", agentFilter.trim());
    if (eventTypeFilter.trim()) search.set("event_type", eventTypeFilter.trim());
    if (routingRoleFilter.trim()) search.set("routing_role", routingRoleFilter.trim());
    if (routingProviderFilter.trim()) search.set("routing_provider", routingProviderFilter.trim());
    if (routingModelFilter.trim()) search.set("routing_model", routingModelFilter.trim());
    if (routingPolicyFilter.trim()) search.set("routing_policy", routingPolicyFilter.trim());
    if (serviceFilter.trim()) search.set("service", serviceFilter.trim());
    if (queryText.trim()) search.set("q", queryText.trim());
    return `/api/ops/logs/query?${search.toString()}`;
  }, [
    agentFilter,
    eventTypeFilter,
    historyWindow,
    queryText,
    routingModelFilter,
    routingProviderFilter,
    routingRoleFilter,
    routingPolicyFilter,
    runIdFilter,
    serviceFilter,
    severity,
    source,
  ]);

  const summary = useFetch<OpsSummary>("/api/ops/summary", {
    pollIntervalMs: paused ? undefined : 5000,
  });
  const sourceStatus = useFetch<Record<string, OpsSourceStatus>>("/api/ops/sources", {
    pollIntervalMs: paused ? undefined : 10000,
  });
  const liveSnapshot = useFetch<LogsPayload>(mode === "live" ? liveLogsPath : null, {
    timeoutMs: 20000,
  });
  const historyLogs = useFetch<LogsPayload>(mode === "history" ? historyLogsPath : null, {
    timeoutMs: 20000,
  });
  const runDetail = useFetch<{ run_id: string; events: OpsTraceEvent[]; count: number }>(
    selectedRunId ? `/api/ops/agent-traces/${encodeURIComponent(selectedRunId)}?limit=160` : null,
    {
      pollIntervalMs: paused || mode === "history" ? undefined : 1400,
      timeoutMs: 20000,
    },
  );

  const logsData = mode === "history"
    ? historyLogs.data
    : liveSnapshot.data || liveEntries.length > 0
      ? {
          entries: liveEntries,
          count: liveEntries.length,
          timestamp: liveSnapshot.data?.timestamp || new Date().toISOString(),
        }
      : null;
  const logsLoading = mode === "history"
    ? historyLogs.loading
    : liveSnapshot.loading && liveEntries.length === 0;
  const logsError = mode === "history"
    ? historyLogs.error
    : [liveSnapshot.error, liveError].filter(Boolean).join(" · ") || null;
  const entries = logsData?.entries ?? [];
  const uniqueRuns = useMemo(
    () => Array.from(new Set(entries.map((entry) => entry.run_id).filter(Boolean))) as string[],
    [entries],
  );
  const historyAvailable = sourceStatus.data?.loki_history?.available ?? false;
  const sourceEntries = useMemo<[string, OpsSourceStatus][]>(() => {
    if (sourceStatus.data) {
      return Object.entries(sourceStatus.data);
    }
    return Object.entries(summary.data?.sources ?? {}).map(
      ([name, enabled]) => [name, { available: enabled, kind: "summary" }],
    );
  }, [sourceStatus.data, summary.data?.sources]);
  const runDetailEvents = useMemo(
    () =>
      (runDetail.data?.events ?? []).filter((event) =>
        matchesRoutingTraceEvent(event, routingFilters),
      ),
    [routingFilters, runDetail.data?.events],
  );
  const mcp = summary.data?.mcp;
  const mcpServers = Object.entries(mcp?.servers ?? {});
  const mcpPrimary = mcp?.primary ?? null;
  const mcpAggregateStatus = mcp?.aggregate_status ?? mcp?.status ?? "pending";
  const mcpPrimaryName = mcp?.primary_server ?? mcpPrimary?.server_name ?? mcp?.server_name ?? "unknown";
  const mcpPrimaryStatus = mcpPrimary?.status ?? mcp?.status ?? "pending";
  const mcpPrimarySurface = mcpPrimary ?? mcp;
  const mcpServerCount = mcp?.server_count ?? mcpServers.length;
  const mcpServersOk = mcp?.servers_ok ?? mcpServers.filter(([, server]) => server.ok).length;
  const mcpDegradedServers = mcp?.degraded_servers ?? [];
  const tempoReady = sourceStatus.data?.tempo_traces?.available ?? summary.data?.observability?.tempo?.ok ?? false;
  const grafanaProxyUrl = summary.data?.observability?.grafana_proxy_url ?? window.location.origin;
  const langfuseProxyUrl = summary.data?.observability?.langfuse_proxy_url ?? window.location.origin;
  const operatorCopilotPayload = useMemo(
    () => ({
      mode: "logs",
      prompt:
        "Cadre cette vue logs/traces comme un incident operateur: priorise les signaux utiles, les causes probables et la prochaine action manuelle.",
      run_id: selectedRunId ?? (runIdFilter.trim() || undefined),
      service: serviceFilter.trim() || undefined,
      severity,
      mcp_server: mcpDegradedServers[0],
      window: mode === "history" ? historyWindow : "live",
      logs: entries.slice(0, 12).map((entry) => ({
        ts: entry.ts,
        source: entry.source,
        service: entry.service,
        severity: entry.severity,
        message: entry.message,
        run_id: entry.run_id,
        agent_name: entry.agent_name,
        event_type: entry.event_type,
      })),
      traces: runDetailEvents.slice(0, 12).map((event) => ({
        ts: event.ts,
        agent_name: event.agent_name,
        event_type: event.event_type,
        message: event.message,
        routing_role: event.routing_role,
        routing_provider: event.routing_provider,
        routing_model: event.routing_model,
        routing_policy: event.routing_policy,
        error: event.error,
      })),
    }),
    [
      entries,
      historyWindow,
      mcpDegradedServers,
      mode,
      runDetailEvents,
      runIdFilter,
      selectedRunId,
      serviceFilter,
      severity,
    ],
  );
  const operatorCopilotFn = useMemo(
    () => () => agentsApi.operatorCopilot(operatorCopilotPayload),
    [operatorCopilotPayload],
  );
  const {
    execute: runOperatorCopilot,
    data: operatorCopilotResult,
    loading: operatorCopilotLoading,
    error: operatorCopilotError,
  } = useApi(operatorCopilotFn);

  useEffect(() => {
    const next = new URLSearchParams();
    if (mode !== "live") next.set("mode", mode);
    if (source !== "all") next.set("source", source);
    if (severity !== "info") next.set("severity", severity);
    if (historyWindow !== "1h") next.set("since", historyWindow);
    if (runIdFilter.trim()) next.set("run_id", runIdFilter.trim());
    if (agentFilter.trim()) next.set("agent_name", agentFilter.trim());
    if (eventTypeFilter.trim()) next.set("event_type", eventTypeFilter.trim());
    if (routingRoleFilter.trim()) next.set("routing_role", routingRoleFilter.trim());
    if (routingProviderFilter.trim()) next.set("routing_provider", routingProviderFilter.trim());
    if (routingModelFilter.trim()) next.set("routing_model", routingModelFilter.trim());
    if (routingPolicyFilter.trim()) next.set("routing_policy", routingPolicyFilter.trim());
    if (serviceFilter.trim()) next.set("service", serviceFilter.trim());
    if (queryText.trim()) next.set("q", queryText.trim());

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true });
    }
  }, [
    agentFilter,
    eventTypeFilter,
    historyWindow,
    mode,
    queryText,
    routingModelFilter,
    routingProviderFilter,
    routingRoleFilter,
    routingPolicyFilter,
    runIdFilter,
    searchParams,
    serviceFilter,
    setSearchParams,
    severity,
    source,
  ]);

  useEffect(() => {
    if (mode !== "live") {
      setLiveStatus("idle");
      return;
    }

    liveSeenIdsRef.current = new Set();
    setLiveEntries([]);
    setLiveError(null);
  }, [
    agentFilter,
    eventTypeFilter,
    mode,
    routingModelFilter,
    routingProviderFilter,
    routingRoleFilter,
    routingPolicyFilter,
    runIdFilter,
    serviceFilter,
    severity,
    source,
  ]);

  useEffect(() => {
    if (mode !== "live" || !liveSnapshot.data) {
      return;
    }

    liveSeenIdsRef.current = new Set(liveSnapshot.data.entries.map((entry) => entry.id));
    setLiveEntries(liveSnapshot.data.entries);
  }, [liveSnapshot.data, mode]);

  useEffect(() => {
    if (mode !== "live") {
      setLiveStatus("idle");
      return;
    }
    if (paused) {
      setLiveStatus("paused");
      return;
    }

    const eventSources: EventSource[] = [];
    const needsLogStream = source !== "agent-trace";
    const needsTraceStream = source === "all" || source === "agent-trace";
    const ready = {
      logs: !needsLogStream,
      traces: !needsTraceStream,
    };
    const syncReadyState = () => {
      if (ready.logs && ready.traces) {
        setLiveStatus("live");
      }
    };
    const pushEntries = (incoming: OpsLogEntry[]) => {
      const filtered = incoming.filter(
        (entry) =>
          severityRank(entry.severity) >= severityRank(severity) &&
          matchesRoutingEntry(entry, routingFilters),
      );
      if (filtered.length === 0) {
        return;
      }
      setLiveEntries((current) => mergeLiveEntries(current, filtered));
      setLiveError(null);
      setLiveStatus("live");
    };

    setLiveStatus("connecting");
    setLiveError(null);

    if (needsLogStream) {
      const logStream = new EventSource(
        opsApi.logStreamPath({
          source,
          severity,
          service: serviceFilter.trim() || undefined,
        }),
      );
      logStream.addEventListener("open", () => {
        ready.logs = true;
        syncReadyState();
      });
      logStream.addEventListener("log", (event) => {
        const entry = parseEventPayload<OpsLogEntry>(event as MessageEvent);
        if (!entry || liveSeenIdsRef.current.has(entry.id)) {
          return;
        }
        liveSeenIdsRef.current.add(entry.id);
        pushEntries([entry]);
      });
      logStream.onerror = () => {
        setLiveError("service/machine stream reconnecting");
        setLiveStatus("connecting");
      };
      eventSources.push(logStream);
    }

    if (needsTraceStream) {
      const traceStream = new EventSource(
        opsApi.agentTraceStreamPath({
          run_id: runIdFilter.trim() || undefined,
          agent_name: agentFilter.trim() || undefined,
          event_type: eventTypeFilter.trim() || undefined,
          limit: 40,
        }),
      );
      traceStream.addEventListener("open", () => {
        ready.traces = true;
        syncReadyState();
      });
      traceStream.addEventListener("agent_trace", (event) => {
        const entry = parseEventPayload<OpsTraceEvent>(event as MessageEvent);
        if (!entry || liveSeenIdsRef.current.has(entry.id)) {
          return;
        }
        liveSeenIdsRef.current.add(entry.id);
        pushEntries([
          {
            id: entry.id,
            ts: entry.ts,
            source: "agent-trace",
            service: "core",
            severity: entry.severity,
            message: entry.message,
            run_id: entry.run_id,
            agent_name: entry.agent_name,
            from_agent: entry.from_agent,
            to_agent: entry.to_agent,
            event_type: entry.event_type,
            labels: {
              mode: entry.mode,
              provider: entry.provider ?? "",
              model: entry.model ?? "",
              routing_role: entry.routing_role ?? "",
              routing_provider: entry.routing_provider ?? "",
              routing_model: entry.routing_model ?? "",
              routing_policy: entry.routing_policy ?? "",
              routing_selected_by: entry.routing_selected_by ?? "",
              routing_transport: entry.routing_transport ?? "",
              routing_latency_ms:
                entry.routing_latency_ms !== undefined && entry.routing_latency_ms !== null
                  ? String(entry.routing_latency_ms)
                  : "",
            },
          },
        ]);
      });
      traceStream.onerror = () => {
        setLiveError("agent trace stream reconnecting");
        setLiveStatus("connecting");
      };
      eventSources.push(traceStream);
    }

    syncReadyState();

    return () => {
      for (const stream of eventSources) {
        stream.close();
      }
    };
  }, [
    agentFilter,
    eventTypeFilter,
    mode,
    paused,
    routingFilters,
    runIdFilter,
    serviceFilter,
    severity,
    source,
  ]);

  useEffect(() => {
    if (uniqueRuns.length === 0) {
      if (selectedRunId) {
        setSelectedRunId(null);
      }
      return;
    }
    if (!selectedRunId || !uniqueRuns.includes(selectedRunId)) {
      setSelectedRunId(uniqueRuns[0]);
    }
  }, [selectedRunId, uniqueRuns]);

  if (logsLoading && !logsData && !summary.data) {
    return (
      <LoadingPanel
        title={mode === "history" ? "Opening log history" : "Opening live logs"}
        message="Collecting recent traces, service incidents and orchestration posture."
      />
    );
  }

  if (logsError && !logsData && !summary.data) {
    return (
      <InlineNotice
        title="logs error"
        message={logsError}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  return (
    <div className="space-y-6">
      {(logsError || summary.error) ? (
        <InlineNotice
          title="live lane degraded"
          message={[logsError, summary.error].filter(Boolean).join(" · ")}
          tone="error"
        />
      ) : null}
      {mode === "history" && !historyAvailable ? (
        <InlineNotice
          title="history unavailable"
          message="Loki n'est pas annonce comme disponible. Les filtres restent prets, mais la requete history ne renverra rien tant que la stack observability n'est pas active."
          tone="error"
          action={
            <div className="flex flex-wrap gap-3">
              <Button
                variant="ghost"
                className="border border-border/80"
                onClick={() => setMode("live")}
              >
                switch to live
              </Button>
              <Link
                to="/ops"
                className="rounded-2xl border border-accent/35 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/10"
              >
                open ops hub
              </Link>
            </div>
          }
        />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(57,255,136,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">live observability</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                Watch agent handoffs and service incidents in one matrix lane
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Cette vue consolide les traces inter-agent du core, les incidents de service remontes par la gateway et, si `ops-agent` est actif, les logs machine/Docker les plus recents. L'historique reste conditionne a Loki.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                  entries {entries.length}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  active runs {summary.data?.traces.active_runs ?? 0}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  source {source}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  mode {mode}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  mcp {mcpAggregateStatus}
                </span>
                <span className={["status-chip", paused ? "border-[#7a2436] bg-[#18070d]/80 text-error" : "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"].join(" ")}>
                  {mode === "history"
                    ? "history query"
                    : paused
                      ? "paused"
                      : liveStatus === "live"
                        ? "live sse"
                        : "sse connecting"}
                </span>
                <span className={["status-chip", historyAvailable ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]" : "border-[#5d2332] bg-[#18070d]/80 text-error"].join(" ")}>
                  loki {historyAvailable ? "ready" : "pending"}
                </span>
                <span className={["status-chip", tempoReady ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]" : "border-[#5d2332] bg-[#18070d]/80 text-error"].join(" ")}>
                  tempo {tempoReady ? "ready" : "pending"}
                </span>
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <Button
                  variant="ghost"
                  className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  disabled={mode === "history"}
                  onClick={() => setPaused((current) => !current)}
                >
                  {mode === "history" ? "history mode" : paused ? "resume feed" : "pause feed"}
                </Button>
                <Button
                  variant="ghost"
                  className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  onClick={() => {
                    void (mode === "history" ? historyLogs.refetch() : liveSnapshot.refetch());
                    void summary.refetch();
                    void sourceStatus.refetch();
                    if (selectedRunId) {
                      void runDetail.refetch();
                    }
                  }}
                >
                  refresh now
                </Button>
                <Link
                  to="/agents/agent-zero"
                  className="rounded-2xl border border-accent/40 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
                >
                  open agent-zero
                </Link>
                <a
                  href={grafanaProxyUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-2xl border border-border/80 bg-black/25 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/78 transition hover:border-accent/35 hover:text-accent"
                >
                  open grafana
                </a>
                <a
                  href={langfuseProxyUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-2xl border border-border/80 bg-black/25 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/78 transition hover:border-accent/35 hover:text-accent"
                >
                  open langfuse
                </a>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">last sync</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {logsData ? formatStamp(logsData.timestamp) : "--:--:--"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Horodatage de la derniere consolidation remontee par la gateway.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">recent runs</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {(summary.data?.traces.recent_runs.length ?? uniqueRuns.length).toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Nombre de runs visibles dans le buffer recent de traces.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">alerts</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-error">
                  {(summary.data?.alerts.length ?? 0).toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Entrees critique/error remontant du monitor et des traces recentes.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">selected run</p>
                <p className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                  {selectedRunId || "none"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  La detail lane suit la run courante selectionnee dans la console.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">source posture</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {sourceEntries.length.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Capacites remontees par la gateway pour journald, docker, Loki, OTel et AgentSight.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <div className="grid gap-4">
          <Card title="Feed filters">
            <div className="space-y-4">
              <Select
                label="Mode"
                value={mode}
                onChange={(event) => setMode(event.target.value as "live" | "history")}
                options={modeOptions}
              />
              <Select
                label="Source"
                value={source}
                onChange={(event) => setSource(event.target.value as typeof source)}
                options={sourceOptions}
              />
              <Select
                label="Severity"
                value={severity}
                onChange={(event) => setSeverity(event.target.value as typeof severity)}
                options={severityOptions}
              />
              <Input
                label="Run id"
                value={runIdFilter}
                onChange={(event) => setRunIdFilter(event.target.value)}
                placeholder="ab12cd34..."
              />
              <Input
                label="Agent filter"
                value={agentFilter}
                onChange={(event) => setAgentFilter(event.target.value)}
                placeholder="agent-zero, planner..."
              />
              <Input
                label="Event type"
                value={eventTypeFilter}
                onChange={(event) => setEventTypeFilter(event.target.value)}
                placeholder="handoff, run_failed..."
              />
              <Input
                label="Routing role"
                value={routingRoleFilter}
                onChange={(event) => setRoutingRoleFilter(event.target.value)}
                placeholder="gpu, general, worker..."
              />
              <Input
                label="Routing provider"
                value={routingProviderFilter}
                onChange={(event) => setRoutingProviderFilter(event.target.value)}
                placeholder="ollama, mistral..."
              />
              <Input
                label="Routing model"
                value={routingModelFilter}
                onChange={(event) => setRoutingModelFilter(event.target.value)}
                placeholder="llama3.2:3b, mistral-large..."
              />
              <Input
                label="Routing policy"
                value={routingPolicyFilter}
                onChange={(event) => setRoutingPolicyFilter(event.target.value)}
                placeholder="auto, strong, cheap, fast..."
              />
              <Input
                label="Service filter"
                value={serviceFilter}
                onChange={(event) => setServiceFilter(event.target.value)}
                placeholder="core, api, postgres..."
              />
              {mode === "history" ? (
                <>
                  <Select
                    label="History window"
                    value={historyWindow}
                    onChange={(event) => setHistoryWindow(event.target.value)}
                    options={historyWindowOptions}
                  />
                  <Input
                    label="Search text"
                    value={queryText}
                    onChange={(event) => setQueryText(event.target.value)}
                    placeholder="failed, exception, handoff..."
                  />
                </>
              ) : null}
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="ghost"
                  className="border border-border/80"
                  onClick={() => {
                    setSource("all");
                    setSeverity("info");
                    setRunIdFilter("");
                    setAgentFilter("");
                    setEventTypeFilter("");
                    setRoutingRoleFilter("");
                    setRoutingProviderFilter("");
                    setRoutingModelFilter("");
                    setRoutingPolicyFilter("");
                    setServiceFilter("");
                    setQueryText("");
                    setHistoryWindow("1h");
                  }}
                >
                  reset filters
                </Button>
                <Link
                  to="/orchestrate"
                  className="rounded-2xl border border-accent/35 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/10"
                >
                  frame with agent-zero
                </Link>
              </div>
            </div>
          </Card>

          <Card title="Incident presets">
            <div className="space-y-4">
              <p className="text-sm leading-7 text-amber-100/58">
                Presets rapides pour basculer entre incidents service, handoffs inter-agents et runs en cours.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="ghost"
                  className="border border-border/80"
                  onClick={() => {
                    setMode("live");
                    setSource("service");
                    setSeverity("warning");
                    setServiceFilter("");
                    setRunIdFilter("");
                  }}
                >
                  service incidents
                </Button>
                <Button
                  variant="ghost"
                  className="border border-border/80"
                  onClick={() => {
                    setMode("live");
                    setSource("agent-trace");
                    setSeverity("info");
                    setServiceFilter("");
                  }}
                >
                  handoffs
                </Button>
                <Button
                  variant="ghost"
                  className="border border-border/80"
                  onClick={() => {
                    if (selectedRunId) {
                      setRunIdFilter(selectedRunId);
                    }
                    setSource("all");
                    setSeverity("info");
                  }}
                >
                  selected run
                </Button>
                <Button
                  variant="ghost"
                  className="border border-border/80"
                  onClick={() => {
                    setMode("history");
                    setSource("all");
                    setSeverity("warning");
                    setHistoryWindow("6h");
                  }}
                >
                  incident history
                </Button>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <a
                  href={`${grafanaProxyUrl}`}
                  target="_blank"
                  rel="noreferrer"
                  className="block rounded-[1.4rem] border border-border/80 bg-black/25 px-4 py-4 transition hover:border-accent/35 hover:bg-black/30"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                    grafana / tempo
                  </p>
                  <p className="mt-2 text-sm text-amber-100/72">{grafanaProxyUrl.replace(/^https?:\/\//, "")}</p>
                  <p className="mt-2 text-[12px] leading-5 text-amber-100/44">
                    Dashboards, search traces Tempo et drilldown metrics.
                  </p>
                </a>
                <a
                  href={`${langfuseProxyUrl}`}
                  target="_blank"
                  rel="noreferrer"
                  className="block rounded-[1.4rem] border border-border/80 bg-black/25 px-4 py-4 transition hover:border-accent/35 hover:bg-black/30"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                    langfuse
                  </p>
                  <p className="mt-2 text-sm text-amber-100/72">{langfuseProxyUrl.replace(/^https?:\/\//, "")}</p>
                  <p className="mt-2 text-[12px] leading-5 text-amber-100/44">
                    LLM traces applicatives et correlation runtime.
                  </p>
                </a>
              </div>
            </div>
          </Card>

          <Card title="Agent Zero Copilot">
            <div className="space-y-4">
              <p className="text-sm leading-7 text-amber-100/58">
                Lance un cadrage opérateur structuré sur le buffer courant: logs, run detail et signaux MCP.
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge color={tempoReady ? "accent" : "warning"}>
                  tempo {tempoReady ? "ready" : "watch"}
                </Badge>
                <Badge color={historyAvailable ? "accent" : "warning"}>
                  loki {historyAvailable ? "ready" : "watch"}
                </Badge>
                <Badge color={mcpTone(mcpAggregateStatus)}>
                  mcp {mcpAggregateStatus}
                </Badge>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={() => {
                    void runOperatorCopilot(undefined);
                  }}
                  loading={operatorCopilotLoading}
                >
                  frame current lane
                </Button>
                <Link
                  to="/agents/agent-zero"
                  className="rounded-2xl border border-border/80 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/72 transition hover:border-accent/35 hover:text-accent"
                >
                  open agent-zero
                </Link>
              </div>
              {operatorCopilotError ? (
                <InlineNotice title="copilot degraded" message={operatorCopilotError} tone="error" />
              ) : null}
              {operatorCopilotResult ? (
                <div className="whitespace-pre-wrap rounded-[1.5rem] border border-border/80 bg-black/25 p-4 text-sm leading-7 text-amber-100/78">
                  {operatorCopilotResult.content}
                </div>
              ) : null}
            </div>
          </Card>

          <Card title="MCP widget">
            {!mcp ? (
              <InlineNotice
                title="mcp pending"
                message="Le resume ops ne contient pas encore de bloc MCP."
              />
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge color={mcpTone(mcpAggregateStatus)}>{mcpAggregateStatus}</Badge>
                  <Badge color={mcpTone(mcpPrimaryStatus)}>{formatMcpName(mcpPrimaryName)}</Badge>
                  {mcpPrimarySurface?.runtime_mode ? (
                    <Badge color="muted">runtime {mcpPrimarySurface.runtime_mode}</Badge>
                  ) : null}
                  {mcpPrimarySurface?.protocol_version ? (
                    <Badge color="muted">protocol {mcpPrimarySurface.protocol_version}</Badge>
                  ) : null}
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted">servers ok</p>
                    <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                      {mcpServersOk} / {mcpServerCount}
                    </p>
                    <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                      Etat global de la suite MCP surveillee.
                    </p>
                  </div>
                  <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted">primary latency</p>
                    <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                      {formatLatency(mcpPrimarySurface?.latency_ms)}
                    </p>
                    <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                      Handshake et listing du serveur MCP primaire.
                    </p>
                  </div>
                </div>
                {mcpDegradedServers.length > 0 ? (
                  <InlineNotice
                    title="degraded servers"
                    message={mcpDegradedServers.map((name) => formatMcpName(name)).join(" / ")}
                  />
                ) : null}
                <div className="space-y-3">
                  {mcpServers.map(([name, server]) => (
                    <div
                      key={name}
                      className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge color={mcpTone(server.status)}>{server.status}</Badge>
                        <Badge color="muted">{formatMcpName(name)}</Badge>
                        {server.runtime_mode ? <Badge color="muted">runtime {server.runtime_mode}</Badge> : null}
                      </div>
                      <p className="mt-3 text-sm leading-6 text-amber-100/72">
                        {summarizeMcpServer(server)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
        <Card title={mode === "history" ? "History console" : "Live console"}>
          {entries.length === 0 ? (
            <EmptyState
              message={
                mode === "history"
                  ? "No history entries match the current filter set."
                  : "No live entries match the current filter set."
              }
            />
          ) : (
            <div className="max-h-[820px] space-y-3 overflow-y-auto pr-1">
              {entries.map((entry) => (
                <button
                  key={entry.id}
                  type="button"
                  onClick={() => {
                    if (entry.run_id) {
                      setSelectedRunId(entry.run_id);
                    }
                  }}
                  className={[
                    "w-full rounded-[1.4rem] border bg-black/45 p-4 text-left transition",
                    "hover:border-accent/30 hover:bg-black/55",
                    severityClasses(entry.severity),
                    selectedRunId && entry.run_id === selectedRunId ? "shadow-[0_0_0_1px_rgba(255,209,102,0.22)]" : "",
                  ].join(" ")}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
                        {formatStamp(entry.ts)}
                      </span>
                      <Badge color={sourceBadgeTone(entry.source)}>{entry.source}</Badge>
                      <span className="status-chip border-border/70 bg-black/35 text-amber-100/66">
                        {entry.severity}
                      </span>
                      {entry.service ? (
                        <span className="status-chip border-border/70 bg-black/35 text-amber-100/66">
                          {entry.service}
                        </span>
                      ) : null}
                      {entry.run_id ? (
                        <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                          run {entry.run_id.slice(0, 8)}
                        </span>
                      ) : null}
                      {entry.agent_name ? (
                        <span className="status-chip border-border/70 bg-black/35 text-amber-100/66">
                          {entry.agent_name}
                        </span>
                      ) : null}
                      {entry.event_type ? (
                        <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">
                          {entry.event_type}
                        </span>
                      ) : null}
                    </div>
                    {entry.from_agent && entry.to_agent ? (
                      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#82ffc1]">
                        {entry.from_agent} → {entry.to_agent}
                      </p>
                    ) : null}
                  </div>
                  <p className="mt-3 font-mono text-[13px] leading-6 text-amber-100/78">
                    {entry.message}
                  </p>
                  {entry.labels?.routing_role ||
                  entry.labels?.routing_provider ||
                  entry.labels?.routing_model ||
                  entry.labels?.routing_selected_by ||
                  entry.labels?.routing_transport ||
                  entry.labels?.routing_latency_ms ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {nonEmptyLabel(entry.labels?.routing_selected_by) ? (
                        <span className="status-chip border-border/70 bg-black/35 text-amber-100/66">
                          route {entry.labels?.routing_selected_by}
                        </span>
                      ) : null}
                      {nonEmptyLabel(entry.labels?.routing_transport) ? (
                        <span className="status-chip border-border/70 bg-black/35 text-amber-100/66">
                          transport {entry.labels?.routing_transport}
                        </span>
                      ) : null}
                      {formatRoutingLatency(entry.labels?.routing_latency_ms) ? (
                        <span className="status-chip border-[#6d5c1c] bg-[#1a1507] text-[#ffd166]">
                          {formatRoutingLatency(entry.labels?.routing_latency_ms)}
                        </span>
                      ) : null}
                      {nonEmptyLabel(entry.labels?.routing_role) ? (
                        <span className="status-chip border-[#6d5c1c] bg-[#1a1507] text-[#ffd166]">
                          role {entry.labels?.routing_role}
                        </span>
                      ) : null}
                      {nonEmptyLabel(entry.labels?.routing_provider) ? (
                        <span className="status-chip border-border/70 bg-black/35 text-amber-100/66">
                          provider {entry.labels?.routing_provider}
                        </span>
                      ) : null}
                      {nonEmptyLabel(entry.labels?.routing_model) ? (
                        <span className="status-chip border-border/70 bg-black/35 text-amber-100/66">
                          model {entry.labels?.routing_model}
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                </button>
              ))}
            </div>
          )}
        </Card>

        <div className="space-y-4">
          <Card title="Run detail">
            {!selectedRunId ? (
              <EmptyState message="Select a run-backed entry to inspect its event timeline." />
            ) : runDetail.loading && !runDetail.data ? (
              <LoadingPanel
                compact
                title="Loading run timeline"
                message={`Fetching recent trace events for ${selectedRunId}.`}
              />
            ) : runDetail.error && !runDetail.data ? (
              <InlineNotice title="run trace error" message={runDetail.error} tone="error" />
            ) : (
              <div className="space-y-3">
                <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                  <p className="screen-label">current run</p>
                  <p className="mt-2 font-mono text-sm uppercase tracking-[0.16em] text-accent">
                    {selectedRunId}
                  </p>
                  <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                    {runDetailEvents.length.toString().padStart(2, "0")} / {(runDetail.data?.count ?? 0).toString().padStart(2, "0")} event(s) visible for this lane.
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Link
                      to="/orchestrate"
                      className="rounded-2xl border border-accent/35 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/10"
                    >
                      open orchestrate
                    </Link>
                    <Link
                      to="/agents/agent-zero"
                      className="rounded-2xl border border-border/80 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/72 transition hover:border-accent/35 hover:text-accent"
                    >
                      frame with agent-zero
                    </Link>
                  </div>
                </div>

                <div className="max-h-[520px] space-y-3 overflow-y-auto pr-1">
                  {runDetailEvents.map((event) => (
                    <div
                      key={event.id}
                      className="rounded-[1.4rem] border border-border/80 bg-black/30 p-4"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
                          {formatStamp(event.ts)}
                        </span>
                        <span className={["text-[11px] font-semibold uppercase tracking-[0.18em]", traceTone(event.event_type)].join(" ")}>
                          {event.event_type}
                        </span>
                        {event.agent_name ? (
                          <Badge color="accent">{event.agent_name}</Badge>
                        ) : null}
                        {event.from_agent && event.to_agent ? (
                          <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#82ffc1]">
                            {event.from_agent} → {event.to_agent}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-3 font-mono text-[13px] leading-6 text-amber-100/74">
                        {event.message}
                      </p>
                      {event.routing_selected_by ||
                      event.routing_transport ||
                      event.routing_latency_ms !== undefined && event.routing_latency_ms !== null ||
                      event.routing_role ||
                      event.routing_provider ||
                      event.routing_model ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {event.routing_selected_by ? (
                            <Badge color="muted">route {event.routing_selected_by}</Badge>
                          ) : null}
                          {event.routing_transport ? (
                            <Badge color="muted">transport {event.routing_transport}</Badge>
                          ) : null}
                          {formatRoutingLatency(event.routing_latency_ms) ? (
                            <Badge color="warning">{formatRoutingLatency(event.routing_latency_ms)}</Badge>
                          ) : null}
                          {event.routing_role ? (
                            <Badge color="warning">role {event.routing_role}</Badge>
                          ) : null}
                          {event.routing_provider ? (
                            <Badge color="muted">provider {event.routing_provider}</Badge>
                          ) : null}
                          {event.routing_model ? (
                            <Badge color="muted">model {event.routing_model}</Badge>
                          ) : null}
                        </div>
                      ) : null}
                      {event.prompt_excerpt ? (
                        <p className="mt-3 text-[12px] leading-5 text-amber-100/42">
                          input: {event.prompt_excerpt}
                        </p>
                      ) : null}
                      {event.content_excerpt ? (
                        <p className="mt-2 text-[12px] leading-5 text-amber-100/42">
                          output: {event.content_excerpt}
                        </p>
                      ) : null}
                      {event.error ? (
                        <p className="mt-2 text-[12px] leading-5 text-error">
                          error: {event.error}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>

          <Card title="Source posture">
            <div className="space-y-3">
              {sourceEntries.map(([name, details]) => (
                <div
                  key={name}
                  className="rounded-3xl border border-border/80 bg-black/25 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                      {name.replace(/_/g, " ")}
                    </p>
                    <Badge color={sourceTone(details.available)}>
                      {details.available ? "ready" : "pending"}
                    </Badge>
                  </div>
                  <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                    kind {details.kind}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>
    </div>
  );
}
