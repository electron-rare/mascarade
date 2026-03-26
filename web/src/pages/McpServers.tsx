import { useMemo } from "react";
import { useFetch } from "../hooks/useFetch";
import { Badge, Button, Card, InlineNotice, JsonView, LoadingPanel } from "../components/ui";

// ── Types ──────────────────────────────────────────────────────────────────

type McpRuntimeStatus = {
  ok: boolean;
  status: "ready" | "degraded" | "failed";
  requested_runtime: string;
  runtime_mode: string | null;
  protocol_version: string | null;
  server_name: string | null;
  tool_count: number;
  resource_count: number;
  prompt_count: number;
  latency_ms: number;
  checks: string[];
  secret_configured?: boolean;
  token_configured?: boolean;
  live_requested?: boolean;
  live_validation?: string | null;
  error?: string;
};

type McpSuitePayload = {
  ok: boolean;
  status: string;
  aggregate_status: "ready" | "degraded" | "failed";
  primary_server: string;
  primary: McpRuntimeStatus;
  server_count: number;
  servers_ok: number;
  degraded_servers: string[];
  servers: Record<string, McpRuntimeStatus>;
};

// ── Helpers ────────────────────────────────────────────────────────────────

function statusColor(status: string): "accent" | "error" {
  return status === "ready" ? "accent" : "error";
}

function statusDot(ok: boolean): string {
  return ok
    ? "bg-[#34c759] shadow-[0_0_6px_rgba(52,199,89,0.5)]"
    : "bg-[#ff3b30] shadow-[0_0_6px_rgba(255,59,48,0.5)]";
}

function statusLabel(status: string): string {
  if (status === "ready") return "healthy";
  if (status === "degraded") return "degraded";
  return "failed";
}

function latencyLabel(ms?: number): string {
  if (!Number.isFinite(ms) || !ms || ms <= 0) return "-";
  return `${Math.round(ms)} ms`;
}

function runtimeLabel(mode: string | null, requested: string): string {
  if (mode) return mode;
  if (requested) return requested;
  return "unknown";
}

// ── Component ──────────────────────────────────────────────────────────────

export default function McpServers() {
  const suite = useFetch<McpSuitePayload>("/api/ops/mcp/summary", {
    pollIntervalMs: 15000,
  });

  const servers = useMemo(() => {
    if (!suite.data?.servers) return [];
    return Object.entries(suite.data.servers)
      .map(([key, server]) => ({ key, ...server }))
      .sort((a, b) => {
        // ready first, then degraded, then failed
        const order = { ready: 0, degraded: 1, failed: 2 } as const;
        const diff =
          (order[a.status] ?? 2) - (order[b.status] ?? 2);
        if (diff !== 0) return diff;
        return a.key.localeCompare(b.key);
      });
  }, [suite.data]);

  const aggregateStatus = suite.data?.aggregate_status ?? "failed";
  const serversOk = suite.data?.servers_ok ?? 0;
  const serverCount = suite.data?.server_count ?? 0;
  const degradedList = suite.data?.degraded_servers ?? [];

  // ── Loading ──────────────────────────────────────────────────────────────

  if (suite.loading && !suite.data) {
    return (
      <LoadingPanel
        title="Loading MCP server inventory"
        message="Probing runtime status for each registered MCP server."
      />
    );
  }

  if (suite.error && !suite.data) {
    return (
      <InlineNotice
        title="MCP probe unavailable"
        message={suite.error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* ── Hero card ────────────────────────────────────────────────────── */}
      <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">
              model context protocol
            </p>
            <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent md:text-5xl">
              MCP Server Fleet
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[#1d1d1f]/60 md:text-[15px]">
              Inventaire des serveurs MCP enregistres dans la stack Mascarade.
              Chaque serveur expose des tools, resources et prompts via le
              protocole MCP standardise.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span
                className={[
                  "status-chip",
                  aggregateStatus === "ready"
                    ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"
                    : "border-[#5d2332] bg-[#18070d]/80 text-error",
                ].join(" ")}
              >
                fleet {statusLabel(aggregateStatus)}
              </span>
              <span className="status-chip border-accent/15 bg-accent/10 text-accent">
                servers {serversOk}/{serverCount}
              </span>
              {degradedList.length > 0 && (
                <span className="status-chip border-[#5d2332] bg-[#18070d]/80 text-error">
                  degraded {degradedList.length}
                </span>
              )}
            </div>
            <div className="mt-6">
              <Button
                variant="ghost"
                className="rounded-2xl border border-[rgba(0,0,0,0.08)] px-4 py-2 text-xs uppercase tracking-[0.18em]"
                onClick={() => void suite.refetch()}
              >
                refresh
              </Button>
            </div>
          </div>

          {/* ── Summary tiles ────────────────────────────────────────────── */}
          <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
            <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">
                fleet state
              </p>
              <p
                className={[
                  "mt-3 text-2xl font-semibold uppercase tracking-[0.12em]",
                  aggregateStatus === "ready" ? "text-[#8cffb7]" : "text-error",
                ].join(" ")}
              >
                {statusLabel(aggregateStatus)}
              </p>
            </div>
            <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">
                servers online
              </p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                {String(serversOk).padStart(2, "0")}/{String(serverCount).padStart(2, "0")}
              </p>
            </div>
            <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">
                total tools
              </p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                {String(
                  servers.reduce((sum, s) => sum + (s.tool_count ?? 0), 0),
                ).padStart(2, "0")}
              </p>
            </div>
            <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">
                primary server
              </p>
              <p className="mt-3 text-sm font-semibold uppercase tracking-[0.12em] text-accent">
                {suite.data?.primary_server ?? "-"}
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* ── Server grid ──────────────────────────────────────────────────── */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {servers.map((server) => (
          <Card key={server.key} className="relative">
            {/* Status dot */}
            <div
              className={[
                "absolute right-5 top-5 h-2.5 w-2.5 rounded-full",
                statusDot(server.ok),
              ].join(" ")}
              title={statusLabel(server.status)}
            />

            {/* Header */}
            <div className="pr-6">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">
                {server.key}
              </p>
              <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                {server.server_name || server.key}
              </p>
            </div>

            {/* Status + runtime badges */}
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge color={statusColor(server.status)}>
                {statusLabel(server.status)}
              </Badge>
              <Badge color="accent">
                {runtimeLabel(server.runtime_mode, server.requested_runtime)}
              </Badge>
              {server.protocol_version && (
                <Badge color="accent">{server.protocol_version}</Badge>
              )}
            </div>

            {/* Counters */}
            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-3 py-3">
                <p className="text-[10px] uppercase tracking-[0.16em] text-muted">
                  tools
                </p>
                <p className="mt-2 text-sm font-semibold text-[#1d1d1f]">
                  {server.tool_count}
                </p>
              </div>
              <div className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-3 py-3">
                <p className="text-[10px] uppercase tracking-[0.16em] text-muted">
                  resources
                </p>
                <p className="mt-2 text-sm font-semibold text-[#1d1d1f]">
                  {server.resource_count}
                </p>
              </div>
              <div className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-3 py-3">
                <p className="text-[10px] uppercase tracking-[0.16em] text-muted">
                  prompts
                </p>
                <p className="mt-2 text-sm font-semibold text-[#1d1d1f]">
                  {server.prompt_count}
                </p>
              </div>
            </div>

            {/* Latency */}
            <div className="mt-3 rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-3 py-3">
              <p className="text-[10px] uppercase tracking-[0.16em] text-muted">
                latency
              </p>
              <p className="mt-2 text-sm text-[#1d1d1f]">
                {latencyLabel(server.latency_ms)}
              </p>
            </div>

            {/* Checks (tool names as badges when available) */}
            {server.checks.length > 0 && (
              <div className="mt-3">
                <p className="text-[10px] uppercase tracking-[0.16em] text-muted">
                  checks
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {server.checks.map((check) => (
                    <span
                      key={check}
                      className="inline-block rounded-full border border-[rgba(0,0,0,0.06)] bg-[#f5f5f7] px-2.5 py-0.5 text-[11px] text-[#1d1d1f]/60"
                    >
                      {check}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Config flags */}
            {(server.secret_configured !== undefined ||
              server.token_configured !== undefined) && (
              <div className="mt-3 flex flex-wrap gap-2">
                {server.secret_configured !== undefined && (
                  <Badge color={server.secret_configured ? "accent" : "error"}>
                    secret {server.secret_configured ? "ok" : "missing"}
                  </Badge>
                )}
                {server.token_configured !== undefined && (
                  <Badge color={server.token_configured ? "accent" : "error"}>
                    token {server.token_configured ? "ok" : "missing"}
                  </Badge>
                )}
              </div>
            )}

            {/* Error */}
            {server.error && (
              <p className="mt-3 rounded-2xl border border-[rgba(255,59,48,0.15)] bg-[rgba(255,59,48,0.04)] px-3 py-2.5 text-[12px] leading-5 text-error">
                {server.error}
              </p>
            )}
          </Card>
        ))}
      </section>

      {/* ── Raw payload ──────────────────────────────────────────────────── */}
      <Card title="Raw MCP suite payload">
        <JsonView data={suite.data ?? {}} />
      </Card>
    </div>
  );
}
