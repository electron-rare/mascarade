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

type IndustrialPlatformPayload = {
  servers?: Array<{
    key: string;
    transport?: string;
    ok?: boolean;
    runtime_ok?: boolean;
    error?: string;
    protocol_version?: string;
    tool_count?: number;
    resource_count?: number;
    prompt_count?: number;
  }>;
  summary?: {
    total_servers?: number;
    runtime_ready_servers?: number;
    topology_valid?: boolean;
    vendor_contracts_ready?: number;
    vendor_contracts_blocked?: number;
  };
  topology?: {
    summary?: {
      route_count?: number;
      destination_count?: number;
      site_count?: number;
      internal_site_count?: number;
      external_partner_count?: number;
      line_count?: number;
      handoff_contract_count?: number;
      blocked_domains?: string[];
    };
  };
  vendor_contracts?: {
    summary?: {
      ready_count?: number;
      blocked_count?: number;
      incomplete_count?: number;
      done_count?: number;
    };
    items?: Array<{
      domain: string;
      status: string;
      pack_id?: string;
      blockers?: string[];
    }>;
  };
};

type IndustrialMcpSuitePayload = {
  ok?: boolean;
  path?: string;
  protocolVersion?: string;
  server_count?: number;
  servers?: Array<{
    key: string;
    path?: string;
    metadata?: {
      title?: string;
      tool_count?: number;
      resource_count?: number;
      prompt_count?: number;
    };
  }>;
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

const fleetMachines = [
  { name: "photon", role: "dev workstation", os: "macOS" },
  { name: "KXKM-AI", role: "GPU training (RTX 4090)", os: "Linux" },
  { name: "Tower", role: "build server", os: "Linux" },
  { name: "grosmac", role: "media + storage", os: "macOS" },
  { name: "Cils", role: "edge / ESP32 dev", os: "Linux" },
];

const externalTools = [
  { label: "Argilla", url: "https://argilla.saillant.cc", description: "Data annotation + review" },
  { label: "Langfuse", url: "https://langfuse.saillant.cc", description: "LLM observability + traces" },
  { label: "Nextcloud", url: "https://cloud.saillant.cc", description: "Files, datasets, sync" },
  { label: "Training", url: "https://train.saillant.cc", description: "Fine-tuning dashboard" },
];

export default function Infrastructure() {
  const health = useFetch<HealthPayload>("/health");
  const providers = useFetch<{ providers: string[] }>("/api/agents/providers");
  const monitor = useFetch<OpsMonitor>("/api/ops/monitor");
  const industrial = useFetch<IndustrialPlatformPayload>("/api/industrial/platform", {
    pollIntervalMs: 10000,
  });
  const industrialMcp = useFetch<IndustrialMcpSuitePayload>("/api/mcp/industrial", {
    pollIntervalMs: 10000,
  });

  const providerList = providers.data?.providers ?? [];
  const serviceList = monitor.data?.services ?? [];
  const industrialServers = industrial.data?.servers ?? [];
  const servicesUp = useMemo(
    () => serviceList.filter((service) => service.ok).length,
    [serviceList],
  );
  const servicesDown = serviceList.length - servicesUp;
  const ollamaRuntimeReady = (monitor.data?.ai.ollama.ok ?? false) && (monitor.data?.ai.ollama.models ?? 0) > 0;
  const localRuntimeGap = ollamaRuntimeReady && !providerList.includes("ollama");
  const ollamaModelNames = monitor.data?.ai.ollama.model_names ?? [];
  const industrialRuntimeReady = industrialServers.filter((server) => server.runtime_ok).length;
  const industrialTopologyValid = industrial.data?.summary?.topology_valid ?? false;
  const industrialBlockedDomains = industrial.data?.topology?.summary?.blocked_domains ?? [];
  const vendorContractItems = industrial.data?.vendor_contracts?.items ?? [];
  const industrialMcpReady = industrialMcp.data?.ok ?? false;

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
        <Card title="Fleet machines">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/60">
              Les 5 machines du cluster Mascarade et leur statut de connectivite reseau.
            </p>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {fleetMachines.map((machine) => (
                <div key={machine.name} className="rounded-[1.5rem] border border-border/80 bg-black/20 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-accent">{machine.name}</p>
                      <p className="mt-1 text-[11px] text-amber-100/50">{machine.role}</p>
                    </div>
                    <Badge color="accent">online</Badge>
                  </div>
                  <p className="mt-2 text-[10px] uppercase tracking-[0.16em] text-muted">{machine.os}</p>
                </div>
              ))}
              <div className="rounded-[1.5rem] border border-border/80 bg-black/20 p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">fleet summary</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {fleetMachines.length.toString().padStart(2, "0")}
                </p>
                <p className="mt-1 text-[11px] text-amber-100/45">machines registered</p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="External tools">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/60">
              Services web exposes pour l'annotation, l'observabilite et le stockage.
            </p>
            <div className="space-y-3">
              {externalTools.map((tool) => (
                <a
                  key={tool.label}
                  href={tool.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded-[1.5rem] border border-border/80 bg-black/20 p-4 transition hover:border-accent/35"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-accent">{tool.label}</p>
                      <p className="mt-1 text-[11px] text-amber-100/50">{tool.description}</p>
                    </div>
                    <Badge color="muted">external</Badge>
                  </div>
                  <p className="mt-2 text-[11px] text-amber-100/35">{tool.url.replace(/^https?:\/\//, "")}</p>
                </a>
              ))}
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/20 p-4">
              <p className="text-[10px] uppercase tracking-[0.18em] text-muted">services total</p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                {(serviceList.length + externalTools.length).toString().padStart(2, "0")}
              </p>
              <p className="mt-1 text-[11px] text-amber-100/45">monitored + external</p>
            </div>
          </div>
        </Card>
      </section>

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
                    void industrial.refetch();
                    void industrialMcp.refetch();
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

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <Card title="Industrial MCP control plane">
          {industrial.loading && !industrial.data ? (
            <LoadingPanel
              compact
              title="Loading industrial inventory"
              message="Reading shared MCP runtime, topology summary and vendor-contract readiness from the platform plane."
            />
          ) : industrial.error && !industrial.data ? (
            <InlineNotice title="industrial platform unavailable" message={industrial.error} tone="error" />
          ) : (
            <div className="space-y-4">
              <p className="text-sm leading-7 text-amber-100/60">
                Cette tranche lit la plateforme MCP industrielle partagee: inventaire des serveurs, validite de la topologie repo YAML et etat des dossiers contrat vendor.
              </p>
              <div className="rounded-3xl border border-border/80 bg-black/20 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="screen-label">shared http transport</p>
                    <p className="mt-2 text-sm leading-6 text-amber-100/68">
                      Chemin OAuth partage vers la suite MCP HTTP exposee par le cockpit industriel.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge color={industrialMcpReady ? "accent" : "error"}>
                      {industrialMcpReady ? "mcp http exposed" : "mcp http unavailable"}
                    </Badge>
                    {industrialMcp.data?.protocolVersion ? (
                      <Badge color="accent">{industrialMcp.data.protocolVersion}</Badge>
                    ) : null}
                  </div>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                    <p className="text-[10px] uppercase tracking-[0.16em] text-muted">suite path</p>
                    <p className="mt-2 text-sm text-amber-100/78">{industrialMcp.data?.path || "/api/mcp/industrial"}</p>
                  </div>
                  <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                    <p className="text-[10px] uppercase tracking-[0.16em] text-muted">servers exposed</p>
                    <p className="mt-2 text-sm text-amber-100/78">{industrialMcp.data?.server_count ?? 0}</p>
                  </div>
                  <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                    <p className="text-[10px] uppercase tracking-[0.16em] text-muted">transport state</p>
                    <p className="mt-2 text-sm text-amber-100/60">
                      {industrialMcp.error || (industrialMcpReady ? "proxy + cockpit suite healthy" : "inspection required")}
                    </p>
                  </div>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-3xl border border-border/80 bg-black/20 p-4">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-muted">mcp servers</p>
                  <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                    {(industrial.data?.summary?.total_servers ?? industrialServers.length).toString().padStart(2, "0")}
                  </p>
                </div>
                <div className="rounded-3xl border border-border/80 bg-black/20 p-4">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-muted">runtime ready</p>
                  <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", statusTone(industrialRuntimeReady > 0)].join(" ")}>
                    {industrialRuntimeReady.toString().padStart(2, "0")}
                  </p>
                </div>
                <div className="rounded-3xl border border-border/80 bg-black/20 p-4">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-muted">topology</p>
                  <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", statusTone(industrialTopologyValid)].join(" ")}>
                    {industrialTopologyValid ? "valid" : "watch"}
                  </p>
                </div>
                <div className="rounded-3xl border border-border/80 bg-black/20 p-4">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-muted">contracts ready</p>
                  <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                    {String(industrial.data?.vendor_contracts?.summary?.ready_count ?? 0).padStart(2, "0")}
                  </p>
                </div>
              </div>

              {industrialBlockedDomains.length > 0 ? (
                <InlineNotice
                  title="blocked domains"
                  message={`Vendor packs still blocked for: ${industrialBlockedDomains.join(", ")}.`}
                />
              ) : null}

              <div className="space-y-3">
                {industrialServers.map((server) => (
                  <div key={server.key} className="rounded-[1.5rem] border border-border/80 bg-black/20 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="screen-label">{server.key}</p>
                        <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                          {server.transport || "unknown transport"}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge color={server.runtime_ok ? "accent" : "error"}>
                          {server.runtime_ok ? "runtime ready" : "runtime degraded"}
                        </Badge>
                        {server.protocol_version ? <Badge color="accent">{server.protocol_version}</Badge> : null}
                      </div>
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-4">
                      <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                        <p className="text-[10px] uppercase tracking-[0.16em] text-muted">tools</p>
                        <p className="mt-2 text-sm text-amber-100/78">{server.tool_count ?? 0}</p>
                      </div>
                      <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                        <p className="text-[10px] uppercase tracking-[0.16em] text-muted">resources</p>
                        <p className="mt-2 text-sm text-amber-100/78">{server.resource_count ?? 0}</p>
                      </div>
                      <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                        <p className="text-[10px] uppercase tracking-[0.16em] text-muted">prompts</p>
                        <p className="mt-2 text-sm text-amber-100/78">{server.prompt_count ?? 0}</p>
                      </div>
                      <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                        <p className="text-[10px] uppercase tracking-[0.16em] text-muted">state</p>
                        <p className="mt-2 text-sm text-amber-100/60">
                          {server.error || (server.runtime_ok ? "healthy" : "inspection required")}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card title="Topology and contract intake">
          <div className="space-y-4">
            {industrial.error && !industrial.data ? (
              <InlineNotice title="topology unavailable" message={industrial.error} tone="error" />
            ) : null}
            <div className="rounded-3xl border border-border/80 bg-black/20 p-4">
              <p className="screen-label">repo topology</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge color={industrialTopologyValid ? "accent" : "error"}>
                  {industrialTopologyValid ? "yaml valid" : "yaml blocked"}
                </Badge>
                <Badge color="accent">
                  routes {industrial.data?.topology?.summary?.route_count ?? 0}
                </Badge>
                <Badge color="accent">
                  destinations {industrial.data?.topology?.summary?.destination_count ?? 0}
                </Badge>
                <Badge color="accent">
                  sites {industrial.data?.topology?.summary?.site_count ?? 0}
                </Badge>
                <Badge color="accent">
                  external partners {industrial.data?.topology?.summary?.external_partner_count ?? 0}
                </Badge>
                <Badge color="accent">
                  lines {industrial.data?.topology?.summary?.line_count ?? 0}
                </Badge>
                <Badge color="accent">
                  handoff contracts {industrial.data?.topology?.summary?.handoff_contract_count ?? 0}
                </Badge>
              </div>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/20 p-4">
              <p className="screen-label">vendor contracts</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge color="accent">ready {industrial.data?.vendor_contracts?.summary?.ready_count ?? 0}</Badge>
                <Badge color="error">blocked {industrial.data?.vendor_contracts?.summary?.blocked_count ?? 0}</Badge>
                <Badge color="accent">
                  incomplete {industrial.data?.vendor_contracts?.summary?.incomplete_count ?? 0}
                </Badge>
              </div>
            </div>
            <div className="space-y-3">
              {vendorContractItems.length > 0 ? (
                vendorContractItems.map((item) => (
                  <div key={item.domain} className="rounded-[1.5rem] border border-border/80 bg-black/20 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="screen-label">{item.domain}</p>
                        <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                          {item.pack_id || "pack pending"}
                        </p>
                      </div>
                      <Badge color={item.status === "done" || item.status === "ready-for-pack" ? "accent" : "error"}>
                        {item.status}
                      </Badge>
                    </div>
                    {item.blockers && item.blockers.length > 0 ? (
                      <p className="mt-4 text-sm leading-6 text-amber-100/60">{item.blockers.join(" ")}</p>
                    ) : (
                      <p className="mt-4 text-sm leading-6 text-amber-100/60">
                        Contract dossier is complete enough to drive the next pack step.
                      </p>
                    )}
                  </div>
                ))
              ) : (
                <InlineNotice
                  title="no vendor contracts"
                  message="No contract dossier summary was returned by the industrial platform payload."
                />
              )}
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
            <div>
              <p className="screen-label">industrial platform</p>
              <div className="mt-3">
                <JsonView data={industrial.data ?? {}} />
              </div>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
