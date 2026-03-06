import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { type OpsLogEntry, type OpsSummary, type OpsTraceEvent } from "../api/ops";
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
  if (source === "service") return "error";
  return "muted";
}

function traceTone(eventType: string | undefined): string {
  if (eventType === "run_failed") return "text-error";
  if (eventType === "handoff") return "text-[#82ffc1]";
  if (eventType === "run_completed") return "text-[#8cffb7]";
  return "text-accent";
}

export default function Logs() {
  const [source, setSource] = useState<"all" | "agent-trace" | "service">("all");
  const [severity, setSeverity] = useState<"debug" | "info" | "warning" | "error" | "critical">("info");
  const [runIdFilter, setRunIdFilter] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [paused, setPaused] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const logsPath = useMemo(() => {
    const search = new URLSearchParams({
      limit: "120",
      source,
      severity,
    });
    if (runIdFilter.trim()) search.set("run_id", runIdFilter.trim());
    if (agentFilter.trim()) search.set("agent_name", agentFilter.trim());
    if (eventTypeFilter.trim()) search.set("event_type", eventTypeFilter.trim());
    return `/api/ops/logs/recent?${search.toString()}`;
  }, [agentFilter, eventTypeFilter, runIdFilter, severity, source]);

  const summary = useFetch<OpsSummary>("/api/ops/summary", {
    pollIntervalMs: paused ? undefined : 5000,
  });
  const logs = useFetch<LogsPayload>(logsPath, {
    pollIntervalMs: paused ? undefined : 1400,
    timeoutMs: 20000,
  });
  const runDetail = useFetch<{ run_id: string; events: OpsTraceEvent[]; count: number }>(
    selectedRunId ? `/api/ops/agent-traces/${encodeURIComponent(selectedRunId)}?limit=160` : null,
    {
      pollIntervalMs: paused ? undefined : 1400,
      timeoutMs: 20000,
    },
  );

  const entries = logs.data?.entries ?? [];
  const uniqueRuns = useMemo(
    () => Array.from(new Set(entries.map((entry) => entry.run_id).filter(Boolean))) as string[],
    [entries],
  );

  useEffect(() => {
    if (!selectedRunId && uniqueRuns.length > 0) {
      setSelectedRunId(uniqueRuns[0]);
    }
  }, [selectedRunId, uniqueRuns]);

  if (logs.loading && !logs.data && !summary.data) {
    return (
      <LoadingPanel
        title="Opening live logs"
        message="Collecting recent traces, service incidents and orchestration posture."
      />
    );
  }

  if (logs.error && !logs.data && !summary.data) {
    return (
      <InlineNotice
        title="logs error"
        message={logs.error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  return (
    <div className="space-y-6">
      {(logs.error || summary.error) ? (
        <InlineNotice
          title="live lane degraded"
          message={[logs.error, summary.error].filter(Boolean).join(" · ")}
          tone="error"
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
                Cette vue consolide les traces inter-agent du core et les incidents de service remontes par la gateway. Les sources machine, Loki, OTel et AgentSight restent signalees mais non actives tant que la couche complementaire n'est pas branchee.
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
                <span className={["status-chip", paused ? "border-[#7a2436] bg-[#18070d]/80 text-error" : "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"].join(" ")}>
                  {paused ? "paused" : "live polling"}
                </span>
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <Button
                  variant="ghost"
                  className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  onClick={() => setPaused((current) => !current)}
                >
                  {paused ? "resume feed" : "pause feed"}
                </Button>
                <Button
                  variant="ghost"
                  className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  onClick={() => {
                    void logs.refetch();
                    void summary.refetch();
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
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">last sync</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {logs.data ? formatStamp(logs.data.timestamp) : "--:--:--"}
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
            </div>
          </div>
        </Card>

        <Card title="Feed filters">
          <div className="space-y-4">
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
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
        <Card title="Live console">
          {entries.length === 0 ? (
            <EmptyState message="No live entries match the current filter set." />
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
                  {(runDetail.data?.events ?? []).map((event) => (
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
              {Object.entries(summary.data?.sources ?? {}).map(([name, enabled]) => (
                <div
                  key={name}
                  className="rounded-3xl border border-border/80 bg-black/25 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                      {name.replace(/_/g, " ")}
                    </p>
                    <Badge color={enabled ? "accent" : "error"}>
                      {enabled ? "ready" : "pending"}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>
    </div>
  );
}
