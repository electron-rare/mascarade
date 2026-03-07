import { Link } from "react-router-dom";
import { useMemo } from "react";
import type { OpsMonitor, OpsSourceStatus, OpsSummary } from "../api/ops";
import { useFetch } from "../hooks/useFetch";
import { getDifyHealthUrl, getDifyOrigin } from "../lib/dify";
import { Badge, Button, Card, CompactModelList, InlineNotice, LoadingPanel } from "../components/ui";

function statusTone(ok: boolean): string {
  return ok ? "text-[#8cffb7]" : "text-error";
}

function chipTone(ok: boolean): string {
  return ok
    ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"
    : "border-[#5d2332] bg-[#18070d]/80 text-error";
}

function formatLatency(ms?: number): string {
  if (!Number.isFinite(ms) || !ms || ms <= 0) return "-";
  return `${Math.round(ms)} ms`;
}

function shortUrl(url: string): string {
  return url.replace(/^https?:\/\//, "");
}

function sourceTone(available: boolean): "accent" | "error" {
  return available ? "accent" : "error";
}

function alertTone(severity: "debug" | "info" | "warning" | "error" | "critical"): "muted" | "warning" | "error" {
  if (severity === "warning") return "warning";
  if (severity === "error" || severity === "critical") return "error";
  return "muted";
}

function logSourceTone(source: "service" | "machine" | "agent-trace" | "docker-event"): "accent" | "warning" | "muted" {
  if (source === "agent-trace") return "accent";
  if (source === "machine") return "warning";
  return "muted";
}

export default function OpsHub() {
  const { data, loading, error, refetch } = useFetch<OpsMonitor>("/api/ops/monitor", {
    pollIntervalMs: 5000,
  });
  const summary = useFetch<OpsSummary>("/api/ops/summary", {
    pollIntervalMs: 5000,
  });
  const sourceStatus = useFetch<Record<string, OpsSourceStatus>>("/api/ops/sources", {
    pollIntervalMs: 10000,
  });

  const links = useMemo(() => {
    const origin = window.location.origin;
    const { protocol, hostname } = window.location;
    return [
      { label: "API health", href: `${origin}/health`, note: "gateway health endpoint" },
      { label: "Ops monitor", href: `${origin}/api/ops/monitor`, note: "consolidated runtime snapshot" },
      { label: "Core health", href: `${origin}/core-health`, note: "core liveness via reverse proxy" },
      { label: "Dify web", href: `${getDifyOrigin()}/`, note: "app builder surface via reverse proxy" },
      { label: "Dify API", href: getDifyHealthUrl(), note: "workflow api health on the main proxy" },
      { label: "Open WebUI", href: `${protocol}//${hostname}:8080/`, note: "local chat surface" },
      { label: "Grafana", href: `${protocol}//${hostname}:3001/`, note: "dashboards and panels" },
      { label: "Prometheus", href: `${protocol}//${hostname}:9090/`, note: "raw metrics store" },
      { label: "Ollama", href: `${protocol}//${hostname}:11434/`, note: "local model runtime" },
    ];
  }, []);

  if (loading && !data) {
    return (
      <LoadingPanel
        title="Opening ops hub"
        message="Collecting the live runtime posture and local service links."
      />
    );
  }

  if (error && !data) {
    return (
      <InlineNotice
        title="ops hub unavailable"
        message={error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  if (!data) return null;

  const services = data.services ?? [];
  const servicesUp = services.filter((service) => service.ok).length;
  const servicesDown = services.length - servicesUp;
  const postureOk = data.gateway.api.ok && data.gateway.core && servicesDown === 0;
  const ollamaModels = data.ai.ollama.model_names ?? [];
  const alerts = summary.data?.alerts.slice(0, 4) ?? [];
  const recentRuns = summary.data?.traces.recent_runs.slice(0, 4) ?? [];
  const cluster = summary.data?.cluster;
  const sourceEntries = Object.entries(sourceStatus.data ?? {});
  const historyReady = sourceStatus.data?.loki_history?.available ?? false;
  const machineReady = sourceStatus.data?.machine_logs?.available ?? false;
  const tracesReady = sourceStatus.data?.agent_traces?.available ?? true;
  const difyWeb = services.find((service) => service.name === "dify-web");
  const difyApi = services.find((service) => service.name === "dify-api");
  const difyWebHref = `${getDifyOrigin()}/`;
  const difyApiHref = getDifyHealthUrl();

  return (
    <div className="space-y-6">
      {error ? (
        <InlineNotice title="ops hub note" message={`Last refresh failed: ${error}`} tone="error" />
      ) : null}
      {summary.error ? (
        <InlineNotice title="summary degraded" message={summary.error} tone="error" />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">ops hub</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                Runtime entrypoint and local service lane
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Cette vue remplace l&apos;ancienne page ops statique. Elle sert de point d&apos;entree operateur
                pour lire l&apos;etat de la stack, ouvrir les outils utiles et verifier les modeles locaux exposes
                par Ollama.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className={["status-chip", chipTone(postureOk)].join(" ")}>
                  posture {postureOk ? "nominal" : "watch"}
                </span>
                <span className={["status-chip", chipTone(data.gateway.api.ok)].join(" ")}>
                  api {data.gateway.api.ok ? "online" : "down"}
                </span>
                <span className={["status-chip", chipTone(data.gateway.core)].join(" ")}>
                  core {data.gateway.core ? "online" : "down"}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  ollama {data.ai.ollama.models} models
                </span>
                <span className={["status-chip", historyReady ? chipTone(true) : chipTone(false)].join(" ")}>
                  loki {historyReady ? "ready" : "pending"}
                </span>
                <span className={["status-chip", machineReady ? chipTone(true) : chipTone(false)].join(" ")}>
                  machine {machineReady ? "wired" : "pending"}
                </span>
                <span className={["status-chip", tracesReady ? chipTone(true) : chipTone(false)].join(" ")}>
                  traces {tracesReady ? "wired" : "pending"}
                </span>
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <Button
                  variant="ghost"
                  className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  onClick={() => {
                    void refetch();
                    void summary.refetch();
                    void sourceStatus.refetch();
                  }}
                >
                  refresh hub
                </Button>
                <Link
                  to="/logs"
                  className="rounded-2xl border border-accent/40 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
                >
                  open logs
                </Link>
                <Link
                  to="/metrics"
                  className="rounded-2xl border border-border/80 bg-black/25 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/78 transition hover:border-accent/35 hover:text-accent"
                >
                  open metrics
                </Link>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">services up</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {servicesUp.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Checks actuellement au vert dans le monitor ops.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">services down</p>
                <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", statusTone(servicesDown === 0)].join(" ")}>
                  {servicesDown.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Les briques en echec remontent ici avant d&apos;ouvrir les logs.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">ollama latency</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {formatLatency(data.ai.ollama.latency_ms)}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Temps de reponse du runtime local sur `/api/tags`.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">qdrant</p>
                <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", statusTone(data.ai.qdrant.ok)].join(" ")}>
                  {data.ai.qdrant.ok ? "ready" : "watch"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  {data.ai.qdrant.collections} collection(s) / {formatLatency(data.ai.qdrant.latency_ms)}
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Quick links" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
          <div className="space-y-3">
            <p className="text-sm leading-7 text-amber-100/60">
              Raccourcis ops utiles quand tu arrives sur la stack depuis le proxy.
            </p>
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                target={link.href.startsWith(window.location.origin) ? undefined : "_blank"}
                rel={link.href.startsWith(window.location.origin) ? undefined : "noreferrer"}
                className="block rounded-[1.4rem] border border-border/80 bg-black/25 px-4 py-4 transition hover:border-accent/35 hover:bg-black/30"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                  {link.label}
                </p>
                <p className="mt-2 text-sm text-amber-100/72">{shortUrl(link.href)}</p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/44">{link.note}</p>
              </a>
            ))}
          </div>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <div className="grid gap-4">
          <Card title="Local model bus">
            <div className="space-y-4">
              <p className="text-sm leading-7 text-amber-100/60">
                Liste compacte des modeles actuellement disponibles dans le runtime Ollama local. Ce bloc sert
                d&apos;equivalent utile a l&apos;ancienne carte `Ollama (11434)` de la page ops statique.
              </p>
              <CompactModelList items={ollamaModels} previewCount={8} />
            </div>
          </Card>

          <Card title="Cluster posture">
            <div className="space-y-4">
              <p className="text-sm leading-7 text-amber-100/60">
                Etat minimal du maillage prive entre noeuds Mascarade. Cette carte reste volontairement compacte:
                elle sert a verifier que le cluster est arme et que les peers repondent.
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-muted">cluster</p>
                  <p className={["mt-3 text-xl font-semibold uppercase tracking-[0.14em]", statusTone(cluster?.enabled ?? false)].join(" ")}>
                    {cluster?.enabled ? "enabled" : "local-only"}
                  </p>
                  <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                    node {cluster?.node_id ?? "n/a"} / role {cluster?.role ?? "n/a"}
                  </p>
                </div>
                <div className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-muted">peers</p>
                  <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                    {cluster?.peers_ok ?? 0} / {cluster?.peers_total ?? 0}
                  </p>
                  <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                    Peers joignables sur le reseau prive.
                  </p>
                </div>
              </div>
              <a
                href="/api/cluster/peers"
                target="_blank"
                rel="noreferrer"
                className="inline-flex rounded-2xl border border-border/80 bg-black/20 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-100/74 transition hover:border-accent/35 hover:text-accent"
              >
                open cluster inventory
              </a>
            </div>
          </Card>

          <Card title="Dify lane">
            <div className="space-y-4">
              <p className="text-sm leading-7 text-amber-100/60">
                Dify est deja dans la stack. Cette carte le rend visible comme surface builder, avec ses deux
                entrees utiles et des raccourcis logs pre-filtres.
              </p>
              <div className="flex flex-wrap gap-2">
                <span className={["status-chip", chipTone(Boolean(difyWeb?.ok))].join(" ")}>
                  dify web {difyWeb?.ok ? "online" : "watch"}
                </span>
                <span className={["status-chip", chipTone(Boolean(difyApi?.ok))].join(" ")}>
                  dify api {difyApi?.ok ? "online" : "watch"}
                </span>
                <span className="status-chip border-border/80 bg-black/25 text-muted">
                  redis + postgres required
                </span>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <a
                  href={difyWebHref}
                  className="block rounded-[1.4rem] border border-border/80 bg-black/25 px-4 py-4 transition hover:border-accent/35 hover:bg-black/30"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                    open dify web
                  </p>
                  <p className="mt-2 text-sm text-amber-100/72">{shortUrl(difyWebHref)}</p>
                  <p className="mt-2 text-[12px] leading-5 text-amber-100/44">
                    {difyWeb
                      ? `http ${difyWeb.status || "-"} / ${formatLatency(difyWeb.latency_ms)}`
                      : "surface builder non detectee dans le monitor"}
                  </p>
                </a>
                <a
                  href={difyApiHref}
                  className="block rounded-[1.4rem] border border-border/80 bg-black/25 px-4 py-4 transition hover:border-accent/35 hover:bg-black/30"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                    open dify api health
                  </p>
                  <p className="mt-2 text-sm text-amber-100/72">{shortUrl(difyApiHref)}</p>
                  <p className="mt-2 text-[12px] leading-5 text-amber-100/44">
                    {difyApi
                      ? `http ${difyApi.status || "-"} / ${formatLatency(difyApi.latency_ms)}`
                      : "endpoint api non detecte dans le monitor"}
                  </p>
                </a>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  to="/logs?service=dify-web"
                  className="rounded-2xl border border-accent/35 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/10"
                >
                  dify web logs
                </Link>
                <Link
                  to="/logs?service=dify-api"
                  className="rounded-2xl border border-accent/35 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/10"
                >
                  dify api logs
                </Link>
                <Link
                  to="/logs?service=dify-worker"
                  className="rounded-2xl border border-border/80 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-100/72 transition hover:border-accent/35 hover:text-accent"
                >
                  dify worker logs
                </Link>
              </div>
            </div>
          </Card>
        </div>

        <Card title="Service posture">
          <div className="space-y-3">
            {services.map((service) => (
              <div
                key={service.name}
                className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="screen-label">{service.name}</p>
                    <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                      {shortUrl(service.url)}
                    </p>
                  </div>
                  <Badge color={service.ok ? "accent" : "error"}>
                    {service.ok ? "online" : "down"}
                  </Badge>
                </div>
                <p className="mt-3 text-[12px] leading-5 text-amber-100/52">
                  http {service.status || "-"} / {formatLatency(service.latency_ms)}
                  {service.error ? ` / ${service.error}` : ""}
                </p>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <Card title="Observability posture">
          {sourceEntries.length === 0 ? (
            <InlineNotice
              title="sources pending"
              message="La gateway n'a pas encore renvoye le detail des sources observability."
            />
          ) : (
            <div className="space-y-3">
              {sourceEntries.map(([name, details]) => (
                <div
                  key={name}
                  className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="screen-label">{name.replace(/_/g, " ")}</p>
                      <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
                        {details.kind}
                      </p>
                    </div>
                    <Badge color={sourceTone(details.available)}>
                      {details.available ? "ready" : "pending"}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <div className="grid gap-4">
          <Card title="Recent alerts">
            {alerts.length === 0 ? (
              <InlineNotice
                title="quiet lane"
                message="Aucune alerte critique recente dans le resume ops."
                tone="success"
              />
            ) : (
              <div className="space-y-3">
                {alerts.map((entry) => (
                  <div
                    key={entry.id}
                    className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge color={alertTone(entry.severity)}>{entry.severity}</Badge>
                      <Badge color={logSourceTone(entry.source)}>{entry.source}</Badge>
                      {entry.service ? <span className="status-chip border-border/80 bg-black/25 text-muted">{entry.service}</span> : null}
                    </div>
                    <p className="mt-3 text-sm leading-6 text-amber-100/72">{entry.message}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="Recent orchestration runs">
            {recentRuns.length === 0 ? (
              <InlineNotice
                title="run lane idle"
                message="Aucune run recente n'est encore presente dans le buffer de traces."
              />
            ) : (
              <div className="space-y-3">
                {recentRuns.map((run) => (
                  <div
                    key={run.run_id}
                    className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                        run {run.run_id.slice(0, 8)}
                      </span>
                      <Badge color={run.event_type === "run_failed" ? "error" : "accent"}>
                        {run.event_type}
                      </Badge>
                      {run.agent_name ? <Badge color="muted">{run.agent_name}</Badge> : null}
                    </div>
                    <p className="mt-3 text-sm leading-6 text-amber-100/72">{run.message}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Link
                        to={`/logs?run_id=${encodeURIComponent(run.run_id)}`}
                        className="rounded-2xl border border-accent/35 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/10"
                      >
                        inspect logs
                      </Link>
                      <Link
                        to="/agents/agent-zero"
                        className="rounded-2xl border border-border/80 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-100/72 transition hover:border-accent/35 hover:text-accent"
                      >
                        frame with zero
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </section>
    </div>
  );
}
