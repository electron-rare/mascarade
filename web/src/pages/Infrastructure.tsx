import { Link } from "react-router-dom";
import { useMemo } from "react";
import { type OpsMonitor } from "../api/ops";
import { useFetch } from "../hooks/useFetch";
import { Badge, Button, Card, CompactModelList, InlineNotice, JsonView, LoadingPanel } from "../components/ui";

type HealthPayload = {
  status?: string;
  core?: {
    status?: string;
    providers?: string[];
    agents?: number;
  };
};

function statusTone(ok: boolean): string {
  return ok ? "text-[#8cffb7]" : "text-error";
}

function chipTone(ok: boolean): string {
  return ok
    ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"
    : "border-[#5d2332] bg-[#18070d]/80 text-error";
}

function latencyLabel(ms?: number): string {
  if (!Number.isFinite(ms) || !ms || ms <= 0) return "-";
  return `${Math.round(ms)} ms`;
}

function shortUrl(url: string): string {
  return url.replace(/^https?:\/\//, "");
}

export default function Infrastructure() {
  const health = useFetch<HealthPayload>("/health");
  const providers = useFetch<{ providers: string[] }>("/api/agents/providers");
  const monitor = useFetch<OpsMonitor>("/api/ops/monitor");

  const providerList = providers.data?.providers ?? [];
  const serviceList = monitor.data?.services ?? [];
  const servicesUp = useMemo(
    () => serviceList.filter((service) => service.ok).length,
    [serviceList],
  );
  const servicesDown = serviceList.length - servicesUp;
  const ollamaRuntimeReady = (monitor.data?.ai.ollama.ok ?? false) && (monitor.data?.ai.ollama.models ?? 0) > 0;
  const localRuntimeGap = ollamaRuntimeReady && !providerList.includes("ollama");
  const ollamaModelNames = monitor.data?.ai.ollama.model_names ?? [];

  if (health.loading && !health.data) {
    return (
      <LoadingPanel
        title="Loading infrastructure map"
        message="Collecting gateway health, provider bus and monitored services."
      />
    );
  }
  if (health.error && !health.data) {
    return (
      <InlineNotice
        title="infrastructure error"
        message={health.error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  const gatewayOk = health.data?.status === "ok";
  const coreProviders = health.data?.core?.providers ?? [];
  const coreAgents = health.data?.core?.agents ?? 0;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">stack map</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                Read the gateway surface, provider bus and exposed service grid
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Cette page sert de lecture structurelle: health brut, providers exposes, map des services suivis par le monitor ops et payloads JSON quand il faut descendre d'un niveau.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className={["status-chip", chipTone(gatewayOk)].join(" ")}>
                  gateway {gatewayOk ? "online" : "degraded"}
                </span>
                <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                  providers {providerList.length}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  services {servicesUp}/{serviceList.length || 0}
                </span>
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <Button
                  variant="ghost"
                  className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  onClick={() => {
                    void health.refetch();
                    void providers.refetch();
                    void monitor.refetch();
                  }}
                >
                  refresh all
                </Button>
                <Link
                  to="/logs"
                  className="rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
                >
                  open logs
                </Link>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">gateway state</p>
                <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", statusTone(gatewayOk)].join(" ")}>
                  {gatewayOk ? "stable" : "watch"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Lecture issue du endpoint `/health` de la gateway.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">core registry</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {coreAgents.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Nombre d'agents remontes par le health du core.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">provider bus</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {providerList.length.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Providers exposes par la gateway pour le routage direct.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">failed services</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-error">
                  {servicesDown.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Nombre de services en echec selon le monitor ops.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Provider bus" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/60">
              Lecture rapide du bus de providers expose par la gateway. Ici on suit les adapters declares pour le routage, pas la liste complete des modeles locaux.
            </p>
            {localRuntimeGap ? (
              <InlineNotice
                title="local runtime not exposed"
                message={`Ollama est joignable avec ${monitor.data?.ai.ollama.models ?? 0} modele(s), mais le core n'expose pas encore \`ollama\` dans le provider bus.`}
              />
            ) : null}
            <div className="flex flex-wrap gap-2">
              {providerList.length > 0 ? (
                providerList.map((provider) => (
                  <Badge key={provider} color="accent">
                    {provider}
                  </Badge>
                ))
              ) : (
                <Badge color="error">no provider exposed</Badge>
              )}
              {ollamaRuntimeReady ? (
                <Badge color={localRuntimeGap ? "error" : "accent"}>
                  ollama runtime {monitor.data?.ai.ollama.models ?? 0} models
                </Badge>
              ) : null}
            </div>
            <CompactModelList items={ollamaModelNames} previewCount={8} />
            <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
              <p className="text-[10px] uppercase tracking-[0.18em] text-muted">core health providers</p>
              <p className="mt-2 text-sm leading-6 text-amber-100/68">
                {coreProviders.length > 0 ? coreProviders.join(", ") : "No provider declared in health payload."}
              </p>
            </div>
          </div>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Card title="Observed service grid">
          {monitor.loading && !monitor.data ? (
            <LoadingPanel
              compact
              title="Syncing monitored services"
              message="Waiting for the ops monitor payload to populate the service grid."
            />
          ) : monitor.error && !monitor.data ? (
            <InlineNotice title="monitor error" message={monitor.error} tone="error" />
          ) : serviceList.length === 0 ? (
            <InlineNotice
              title="empty monitor"
              message="No monitored services were returned by the ops monitor payload."
            />
          ) : (
            <div className="space-y-3">
              {serviceList.map((service) => (
                <div
                  key={service.name}
                  className="rounded-[1.5rem] border border-border/80 bg-black/25 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
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
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted">http</p>
                      <p className="mt-2 text-sm text-amber-100/78">{service.status || "-"}</p>
                    </div>
                    <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted">latency</p>
                      <p className="mt-2 text-sm text-amber-100/78">{latencyLabel(service.latency_ms)}</p>
                    </div>
                    <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted">note</p>
                      <p className="mt-2 text-sm text-amber-100/60">
                        {service.error || (service.ok ? "healthy" : "no details")}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Raw payloads">
          <div className="space-y-4">
            <div>
              <p className="screen-label">health</p>
              <div className="mt-3">
                <JsonView data={health.data ?? {}} />
              </div>
            </div>
            <div>
              <p className="screen-label">providers</p>
              <div className="mt-3">
                <JsonView data={providers.data ?? {}} />
              </div>
            </div>
            <div>
              <p className="screen-label">ops monitor</p>
              <div className="mt-3">
                <JsonView data={monitor.data ?? {}} />
              </div>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
