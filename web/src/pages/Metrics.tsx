import { Link } from "react-router-dom";
import { useMemo } from "react";
import type { OpsMonitor } from "../api/ops";
import { useFetch } from "../hooks/useFetch";
import { Badge, Button, Card, InlineNotice, JsonView, LoadingPanel } from "../components/ui";

function statusTone(ok: boolean): string {
  return ok ? "text-[#8cffb7]" : "text-error";
}

function chipTone(ok: boolean): string {
  return ok
    ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"
    : "border-[#5d2332] bg-[#18070d]/80 text-error";
}

function formatLatency(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return "-";
  return `${Math.round(ms)} ms`;
}

function formatStamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function ServicePill({ label, ok }: { label: string; ok: boolean }) {
  return <span className={["status-chip", chipTone(ok)].join(" ")}>{label}</span>;
}

function MetricPanel({
  title,
  subtitle,
  ok,
  primary,
  secondary,
  tertiary,
}: {
  title: string;
  subtitle: string;
  ok: boolean;
  primary: string;
  secondary: string;
  tertiary: string;
}) {
  return (
    <Card className="h-full bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(6,7,7,0.98))]">
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="screen-label">{title}</p>
            <p className="mt-3 text-sm leading-6 text-amber-100/54">{subtitle}</p>
          </div>
          <span className={["status-chip", chipTone(ok)].join(" ")}>{ok ? "online" : "down"}</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-muted">state</p>
            <p className={["mt-3 text-xl font-semibold uppercase tracking-[0.14em]", statusTone(ok)].join(" ")}>
              {primary}
            </p>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-muted">depth</p>
            <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">{secondary}</p>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-muted">latency</p>
            <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">{tertiary}</p>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default function Metrics() {
  const { data, loading, error, refetch } = useFetch<OpsMonitor>(
    "/api/ops/monitor",
    { pollIntervalMs: 5000 },
  );

  const services = data?.services ?? [];
  const servicesUp = useMemo(() => services.filter((svc) => svc.ok).length, [services]);
  const servicesDown = services.length - servicesUp;
  const postureOk = !!data && data.gateway.api.ok && data.gateway.core && servicesDown === 0;

  if (loading && !data) {
    return (
      <LoadingPanel
        title="Syncing metrics"
        message="Collecting the consolidated ops snapshot from the gateway."
      />
    );
  }
  if (error && !data) {
    return (
      <InlineNotice
        title="monitor error"
        message={error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">ops pulse</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                {postureOk ? "Runtime lanes stable" : "Intervention lane open"}
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Derniere synchronisation a {formatStamp(data.timestamp)}. Cette vue agrège l'etat de la gateway, des briques IA et des services exposes pour decider vite ou intervenir.
              </p>

              <div className="mt-5 flex flex-wrap items-center gap-2">
                <ServicePill label={`api ${data.gateway.api.ok ? "online" : "down"}`} ok={data.gateway.api.ok} />
                <ServicePill label={`core ${data.gateway.core ? "online" : "down"}`} ok={data.gateway.core} />
                <ServicePill label={`services ${servicesUp}/${services.length}`} ok={servicesDown === 0} />
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <Button
                  variant="ghost"
                  className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  onClick={() => void refetch()}
                >
                  refresh monitor
                </Button>
                <a
                  href="#services-health"
                  className="rounded-2xl border border-accent/40 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
                >
                  inspect services
                </a>
                <Link
                  to="/logs"
                  className="rounded-2xl border border-border/80 bg-black/25 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/78 transition hover:border-accent/35 hover:text-accent"
                >
                  open logs
                </Link>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">stack posture</p>
                <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", statusTone(postureOk)].join(" ")}>
                  {postureOk ? "nominal" : "watch"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Etat global calcule a partir de la gateway et des checks services exposes.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">services up</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {servicesUp.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Nombre de checks HTTP actuellement au vert dans le monitor ops.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">services down</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-error">
                  {servicesDown.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Les checks en echec sont prioritaires avant toute lecture detaillee des metriques brutes.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">sample clock</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {formatStamp(data.timestamp)}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Horodatage de la derniere lecture consolidee remontee par l'API ops.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Alert lane" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/60">
              Ce resume se concentre sur les points qui cassent le plus vite l'experience operateur: gateway, services indisponibles et exposition des metriques du core.
            </p>
            <div className="space-y-3">
              <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">gateway</p>
                <p className={["mt-2 text-lg font-semibold uppercase tracking-[0.14em]", statusTone(data.gateway.api.ok && data.gateway.core)].join(" ")}>
                  {data.gateway.api.ok && data.gateway.core ? "path clear" : "attention required"}
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">failed services</p>
                <p className="mt-2 text-lg font-semibold uppercase tracking-[0.14em] text-error">
                  {servicesDown === 0 ? "none" : services.filter((svc) => !svc.ok).map((svc) => svc.name).join(", ")}
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">core metrics</p>
                <p className={["mt-2 text-lg font-semibold uppercase tracking-[0.14em]", statusTone(data.core_metrics.ok)].join(" ")}>
                  {data.core_metrics.ok ? "available" : `missing (${data.core_metrics.status})`}
                </p>
                {!data.core_metrics.ok && data.core_metrics.error ? (
                  <p className="mt-2 text-[12px] leading-5 text-amber-100/48">{data.core_metrics.error}</p>
                ) : null}
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">incident framing</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Link
                    to="/logs"
                    className="rounded-2xl border border-accent/35 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/10"
                  >
                    open logs
                  </Link>
                  <Link
                    to="/agents/agent-zero"
                    className="rounded-2xl border border-border/80 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-100/72 transition hover:border-accent/35 hover:text-accent"
                  >
                    agent-zero
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <MetricPanel
          title="Gateway"
          subtitle="Facade HTTP et connexion vers le core Mascarade."
          ok={data.gateway.api.ok && data.gateway.core}
          primary={data.gateway.api.ok && data.gateway.core ? "stable" : "degraded"}
          secondary={`http ${data.gateway.api.status}`}
          tertiary={data.gateway.core ? "core linked" : "core missing"}
        />
        <MetricPanel
          title="AI services"
          subtitle="Lecture synthetique des briques IA les plus sensibles a la latence."
          ok={data.ai.ollama.ok && data.ai.qdrant.ok}
          primary={data.ai.ollama.ok && data.ai.qdrant.ok ? "ready" : "partial"}
          secondary={`${data.ai.ollama.models} models / ${data.ai.qdrant.collections} collections`}
          tertiary={`${formatLatency(data.ai.ollama.latency_ms)} / ${formatLatency(data.ai.qdrant.latency_ms)}`}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <div id="services-health">
          <Card title="Services health table">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-xs">
                <thead>
                  <tr className="border-b border-border text-[10px] uppercase tracking-[0.18em] text-muted">
                    <th className="py-3 text-left">service</th>
                    <th className="py-3 text-left">status</th>
                    <th className="py-3 text-left">http</th>
                    <th className="py-3 text-left">latency</th>
                    <th className="py-3 text-left">target</th>
                    <th className="py-3 text-left">note</th>
                  </tr>
                </thead>
                <tbody>
                  {services.map((svc) => (
                    <tr key={svc.name} className="border-b border-border/50 align-top">
                      <td className="py-3 text-accent uppercase glow-text">{svc.name}</td>
                      <td className={`py-3 ${statusTone(svc.ok)}`}>
                        <span className={`pulse-dot mr-2 ${svc.ok ? "pulse-dot-ok" : "pulse-dot-err"}`} />
                        {svc.ok ? "ONLINE" : "DOWN"}
                      </td>
                      <td className="py-3 text-amber-100/74">{svc.status || "-"}</td>
                      <td className="py-3 text-amber-100/74">{formatLatency(svc.latency_ms)}</td>
                      <td className="py-3 text-amber-100/45">{svc.url}</td>
                      <td className="py-3 text-amber-100/45">{svc.error || (svc.ok ? "healthy" : "no details")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        <Card title="Core metrics payload">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge color={data.core_metrics.ok ? "accent" : "error"}>
                {data.core_metrics.ok ? "metrics available" : "metrics unavailable"}
              </Badge>
              <Badge color="muted">status {data.core_metrics.status}</Badge>
            </div>
            {data.core_metrics.ok ? (
              <JsonView data={data.core_metrics.data ?? {}} />
            ) : (
              <InlineNotice
                title="core metrics unavailable"
                message={`Status ${data.core_metrics.status}. ${data.core_metrics.error || "No extra error details were returned."}`}
                tone="error"
              />
            )}
          </div>
        </Card>
      </section>

      {error ? (
        <InlineNotice
          title="polling note"
          message={`Derniere erreur remontee pendant le polling: ${error}`}
          tone="error"
        />
      ) : null}
    </div>
  );
}
