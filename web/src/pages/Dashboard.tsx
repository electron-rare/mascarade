import { Link } from "react-router-dom";
import { type OpsMonitor } from "../api/ops";
import { useFetch } from "../hooks/useFetch";
import { getDifyHealthUrl, getDifyOrigin } from "../lib/dify";
import { Badge, Button, Card, CompactModelList, InlineNotice, LoadingPanel } from "../components/ui";

interface HealthData {
  status: string;
  core: { status: string; providers: string[]; agents: number };
}

const actionCards = [
  {
    to: "/agents/agent-zero",
    label: "Lead agent",
    title: "Open Agent Zero",
    body: "Point d'entree generaliste pour cadrer une demande, la decomposer et prioriser la prochaine action.",
  },
  {
    to: "/playground",
    label: "Prompt lane",
    title: "Open Playground",
    body: "Tester rapidement les prompts et verifier la reponse du routage principal.",
  },
  {
    to: "/agents",
    label: "Registry",
    title: "Inspect Agents",
    body: "Lister les agents exposes et basculer vers la vue detaillee quand un comportement derive.",
  },
  {
    to: "/training",
    label: "Training",
    title: "Training Deck",
    body: "Monitoring du training, datasets et benchmark des modeles fine-tunes.",
  },
  {
    to: "/admin",
    label: "Admin",
    title: "Control Panel",
    body: "Services, fleet sync, settings, MCP servers, users et audit centralises.",
  },
];

const externalServices = [
  {
    label: "Grafana — Ops Overview",
    url: "https://grafana.saillant.cc/d/6114d2e8-48f0-4e72-86d9-2fbe181a7869/mascarade-ops-overview",
    description: "Metrics, services, latency",
  },
  {
    label: "Grafana — AI Runtime",
    url: "https://grafana.saillant.cc/d/96c8f781-3e6c-4880-9bbf-b368277b9b95/mascarade-ai-runtime",
    description: "Agent metrics, routing, providers",
  },
  {
    label: "Grafana — Fine-Tuning",
    url: "https://grafana.saillant.cc/d/873d0797-744c-4784-a55c-6a97579ab36c/fine-tuning-progress",
    description: "Training progress, GPU, loss curves",
  },
  {
    label: "Grafana — Logs",
    url: "https://grafana.saillant.cc/d/f43f440a-bb15-40cf-a956-a06a56a376e0/mascarade-service-logs",
    description: "Service logs via Loki",
  },
  {
    label: "Grafana — Cost Tracking",
    url: "https://grafana.saillant.cc/d/2595b749-cd76-462b-ac70-a025648b9218/mascarade-cost-tracking",
    description: "LLM costs, token usage",
  },
  {
    label: "Grafana — Leaderboard",
    url: "https://grafana.saillant.cc/d/2cbdd4c5-6b4d-4bd1-9420-46d3e84c0954/mascarade-model-leaderboard",
    description: "Model benchmark scores",
  },
  {
    label: "Langfuse",
    url: "https://langfuse.saillant.cc",
    description: "Agent traces, cost tracking",
  },
  {
    label: "Argilla",
    url: "https://argilla.saillant.cc",
    description: "Dataset review (67K examples)",
  },
  {
    label: "Nextcloud",
    url: "https://cloud.saillant.cc",
    description: "Datasets, models, docs",
  },
  {
    label: "Data Reviewer",
    url: "https://train.saillant.cc",
    description: "Quick dataset preview",
  },
];

type ClusterPayload = {
  nodes?: Array<{
    name?: string;
    status?: string;
  }>;
};

type TrainingStatusData = {
  active?: boolean;
  model_name?: string;
  progress_pct?: number;
  current_loss?: number;
  epoch?: number;
  total_epochs?: number;
};

function headline(status: string) {
  return status === "ok" ? "System matrix stable" : "Gateway under pressure";
}

function narrative(status: string, providers: string[], agents: number) {
  if (status === "ok") {
    return `${providers.length} provider(s) actifs et ${agents} agent(s) disponibles dans la matrice locale.`;
  }

  return "Une ou plusieurs briques ne repondent plus normalement. Priorite: verifier la gateway et les providers actives.";
}

export default function Dashboard() {
  const { data, loading, error, refetch } = useFetch<HealthData>("/health");
  const monitor = useFetch<OpsMonitor>("/api/ops/monitor", { pollIntervalMs: 6000 });
  const cluster = useFetch<ClusterPayload>("/api/cluster/nodes", { pollIntervalMs: 30000 });
  const trainingStatus = useFetch<TrainingStatusData>("/api/ops/training", { pollIntervalMs: 15000 });

  const fleetNodes = cluster.data?.nodes ?? [];
  const fleetOnline = fleetNodes.filter((n) => n.status === "online").length;
  const fleetTotal = fleetNodes.length || 5;

  if (loading && !data) {
    return (
      <LoadingPanel
        title="Syncing dashboard"
        message="Collecting gateway health, provider posture and registry density."
      />
    );
  }
  if (error && !data) {
    return (
      <InlineNotice
        title="dashboard error"
        message={error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }
  if (!data) return null;

  const core = data.core;
  const isUp = typeof core === "object" && core.status === "ok";
  const providers = isUp ? core.providers : [];
  const agents = isUp ? core.agents : 0;
  const statusTone = data.status === "ok" ? "text-[#8cffb7]" : "text-error";
  const ollamaRuntimeReady = (monitor.data?.ai.ollama.ok ?? false) && (monitor.data?.ai.ollama.models ?? 0) > 0;
  const ollamaExposed = providers.includes("ollama");
  const localRuntimeGap = ollamaRuntimeReady && !ollamaExposed;
  const ollamaModelNames = monitor.data?.ai.ollama.model_names ?? [];
  const difyWeb = monitor.data?.services.find((service) => service.name === "dify-web");
  const difyApi = monitor.data?.services.find((service) => service.name === "dify-api");
  const difyWebHref = `${getDifyOrigin()}/`;
  const difyApiHref = getDifyHealthUrl();

  return (
    <div className="space-y-6">
      {error ? (
        <InlineNotice
          title="dashboard note"
          message={`Last refresh failed: ${error}`}
          tone="error"
        />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(9,14,11,0.9)_26%,rgba(7,7,7,0.95))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">runtime posture</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                {headline(data.status)}
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/62 md:text-[15px]">
                {narrative(data.status, providers, agents)}
              </p>
              <div className="mt-5 flex flex-wrap items-center gap-2">
                <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                  gateway {data.status === "ok" ? "healthy" : "degraded"}
                </span>
                <span className={["status-chip", data.status === "ok" ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]" : "border-[#5d2332] bg-[#18070d]/80 text-error"].join(" ")}>
                  core {isUp ? "online" : "offline"}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  providers {providers.length}
                </span>
                {ollamaRuntimeReady ? (
                  <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">
                    ollama {monitor.data?.ai.ollama.models ?? 0} models
                  </span>
                ) : null}
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  agents {agents}
                </span>
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link
                  to="/playground"
                  className="rounded-2xl border border-accent/40 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
                >
                  open playground
                </Link>
                <Link
                  to="/admin"
                  className="rounded-2xl border border-border/80 bg-black/25 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/78 transition hover:border-accent/35 hover:text-accent"
                >
                  admin panel
                </Link>
                <Link
                  to="/training"
                  className="rounded-2xl border border-border/80 bg-black/25 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/78 transition hover:border-accent/35 hover:text-accent"
                >
                  training deck
                </Link>
                <Button variant="ghost" className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]" onClick={() => void refetch()}>
                  refresh status
                </Button>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">health signal</p>
                <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", statusTone].join(" ")}>
                  {data.status === "ok" ? "nominal" : "degraded"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
                  Gateway and shell alignment for the current routing layer.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">provider bus</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {providers.length.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
                  Active adapters currently exposed by the core health endpoint.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">agent registry</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {agents.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
                  Registered agent surfaces ready for inspection or orchestration.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">dispatch mode</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  local
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
                  Cockpit branche sur la gateway Mascarade et sur le core en amont.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Provider bus" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
          <div className="space-y-5">
            <div>
              <p className="text-sm leading-7 text-amber-100/62">
                Le provider bus liste les adapters enregistres par le core, pas les modeles individuels. Les LLM locaux apparaissent ici via `ollama` ou `apple-local` quand le routage core les expose.
              </p>
            </div>

            {localRuntimeGap ? (
              <InlineNotice
                title="local runtime detected"
                message={`Ollama repond avec ${monitor.data?.ai.ollama.models ?? 0} modele(s), mais le core ne publie pas encore l'adapter \`ollama\` dans le provider bus. Verifie \`OLLAMA_ENABLED=true\` et \`OLLAMA_BASE_URL=http://ollama:11434\`, puis redemarre le core.`}
              />
            ) : null}

            <div className="flex flex-wrap gap-2">
              {providers.length > 0 ? (
                providers.map((provider) => (
                  <Badge key={provider} color="accent">
                    {provider}
                  </Badge>
                ))
              ) : (
                <Badge color="error">no provider detected</Badge>
              )}
              {ollamaRuntimeReady && !ollamaExposed ? (
                <Badge color="error">ollama runtime only</Badge>
              ) : null}
            </div>

            <CompactModelList items={ollamaModelNames} />

            <div className="space-y-3 rounded-3xl border border-border/80 bg-black/25 p-4">
              <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.18em]">
                <span className="text-muted">signal</span>
                <span className={statusTone}>{data.status === "ok" ? "stable" : "needs attention"}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-black/40">
                <div
                  className={[
                    "h-full rounded-full transition-all",
                    data.status === "ok"
                      ? "bg-[linear-gradient(90deg,#39ff88,#ffd166)]"
                      : "bg-[linear-gradient(90deg,#ff3b5c,#ffd166)]",
                  ].join(" ")}
                  style={{ width: `${Math.max(18, Math.min(100, providers.length * 18 || 22))}%` }}
                />
              </div>
              <p className="text-[12px] leading-5 text-amber-100/46">
                Densite calculee a partir du nombre de providers exposes dans le health check courant.
              </p>
            </div>
          </div>
        </Card>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {actionCards.map((card) => (
          <Link
            key={card.to}
            to={card.to}
            className="group rounded-[1.75rem] border border-border/80 bg-[linear-gradient(180deg,rgba(9,9,9,0.88),rgba(6,7,7,0.98))] p-5 transition duration-200 hover:border-accent/35 hover:bg-[linear-gradient(180deg,rgba(255,209,102,0.06),rgba(8,9,8,0.98))]"
          >
            <p className="screen-label">{card.label}</p>
            <h3 className="mt-3 text-lg font-semibold uppercase tracking-[0.12em] text-accent transition group-hover:glow-text">
              {card.title}
            </h3>
            <p className="mt-3 text-sm leading-7 text-amber-100/54">{card.body}</p>
            <p className="mt-6 text-[11px] uppercase tracking-[0.18em] text-amber-100/36 transition group-hover:text-accent">
              enter module
            </p>
          </Link>
        ))}
      </section>

      {/* Fleet + Training summaries */}
      <section className="grid gap-4 xl:grid-cols-2">
        <Card title="Fleet status">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/60">
              Vue rapide du cluster. Detail complet dans Admin &gt; Fleet.
            </p>
            <div className="flex flex-wrap gap-2">
              <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                machines {fleetTotal}
              </span>
              <span className={["status-chip", fleetOnline > 0 ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]" : "border-[#5d2332] bg-[#18070d]/80 text-error"].join(" ")}>
                online {fleetOnline}
              </span>
            </div>
            <Link
              to="/admin"
              className="inline-block rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
            >
              open fleet
            </Link>
          </div>
        </Card>

        <Card title="Training status">
          <div className="space-y-4">
            {trainingStatus.data?.active ? (
              <>
                <p className="text-sm leading-7 text-amber-100/60">
                  Training en cours: {trainingStatus.data.model_name || "model"} — epoch {trainingStatus.data.epoch ?? "-"}/{trainingStatus.data.total_epochs ?? "-"}
                </p>
                <div className="flex flex-wrap gap-2">
                  <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">
                    active
                  </span>
                  <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                    {trainingStatus.data.progress_pct?.toFixed(1) ?? "-"}%
                  </span>
                  <span className="status-chip border-border/80 bg-black/30 text-muted">
                    loss {trainingStatus.data.current_loss?.toFixed(4) ?? "-"}
                  </span>
                </div>
              </>
            ) : (
              <p className="text-sm leading-7 text-amber-100/60">
                Aucun training actif. Le worker attend un nouveau run.
              </p>
            )}
            <Link
              to="/training"
              className="inline-block rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
            >
              open training
            </Link>
          </div>
        </Card>
      </section>

      {/* External services */}
      <section>
        <Card title="Services externes">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/60">
              Services web exposes pour le monitoring, l'observabilite, le stockage et la generation d'images.
            </p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {externalServices.map((svc) => (
                <a
                  key={svc.label}
                  href={svc.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group rounded-[1.4rem] border border-border/80 bg-black/20 p-4 transition hover:border-accent/35"
                >
                  <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-accent transition group-hover:glow-text">
                    {svc.label}
                  </p>
                  <p className="mt-1 text-[11px] text-amber-100/50">{svc.description}</p>
                  <p className="mt-2 text-[10px] text-amber-100/30">{svc.url.replace(/^https?:\/\//, "")}</p>
                </a>
              ))}
            </div>
          </div>
        </Card>
      </section>

      {/* Agent Zero lane */}
      <section className="grid gap-4 xl:grid-cols-2">
        <Card
          title="Agent Zero lane"
          className="bg-[linear-gradient(180deg,rgba(255,209,102,0.06),rgba(8,9,8,0.98))]"
        >
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/60">
              Porte d&apos;entree recommandee pour cadrer une demande floue, decomposer une action et basculer
              ensuite vers les lanes specialisees.
            </p>
            <div className="flex flex-wrap gap-2">
              <span className="status-chip border-accent/35 bg-accent/10 text-accent">lead workflow</span>
              <span className="status-chip border-border/80 bg-black/25 text-muted">intake + triage</span>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Link
                to="/agents/agent-zero"
                className="rounded-[1.4rem] border border-accent/35 bg-black/25 px-4 py-4 transition hover:bg-accent/10"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                  open agent zero
                </p>
                <p className="mt-2 text-sm text-amber-100/72">/agents/agent-zero</p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/44">
                  Vue detaillee, usages recommandes et acces direct au run lane.
                </p>
              </Link>
              <Link
                to="/playground"
                className="rounded-[1.4rem] border border-border/80 bg-black/25 px-4 py-4 transition hover:border-accent/35 hover:bg-black/30"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                  open playground
                </p>
                <p className="mt-2 text-sm text-amber-100/72">prompt sandbox</p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/44">
                  Tester rapidement les prompts et verifier la reponse du routage principal.
                </p>
              </Link>
            </div>
          </div>
        </Card>

        <Card title="Dify lane">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/60">
              Surface builder deja presente dans la stack pour les workflows IA, avec acces web et health API.
            </p>
            <div className="flex flex-wrap gap-2">
              <span
                className={[
                  "status-chip",
                  difyWeb?.ok
                    ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"
                    : "border-[#5d2332] bg-[#18070d]/80 text-error",
                ].join(" ")}
              >
                dify web {difyWeb?.ok ? "online" : "watch"}
              </span>
              <span
                className={[
                  "status-chip",
                  difyApi?.ok
                    ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"
                    : "border-[#5d2332] bg-[#18070d]/80 text-error",
                ].join(" ")}
              >
                dify api {difyApi?.ok ? "online" : "watch"}
              </span>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <a
                href={difyWebHref}
                target="_blank"
                rel="noreferrer"
                className="rounded-[1.4rem] border border-border/80 bg-black/25 px-4 py-4 transition hover:border-accent/35 hover:bg-black/30"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                  open dify web
                </p>
                <p className="mt-2 text-sm text-amber-100/72">{difyWebHref.replace(/^https?:\/\//, "")}</p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/44">
                  {difyWeb ? `http ${difyWeb.status || "-"} / ${Math.round(difyWeb.latency_ms || 0)} ms` : "surface builder pending"}
                </p>
              </a>
              <a
                href={difyApiHref}
                target="_blank"
                rel="noreferrer"
                className="rounded-[1.4rem] border border-border/80 bg-black/25 px-4 py-4 transition hover:border-accent/35 hover:bg-black/30"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                  open dify api
                </p>
                <p className="mt-2 text-sm text-amber-100/72">{difyApiHref.replace(/^https?:\/\//, "")}</p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/44">
                  {difyApi ? `http ${difyApi.status || "-"} / ${Math.round(difyApi.latency_ms || 0)} ms` : "workflow api pending"}
                </p>
              </a>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
