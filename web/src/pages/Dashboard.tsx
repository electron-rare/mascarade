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
    to: "/admin",
    label: "Ops",
    title: "Check Metrics",
    body: "Confirmer la sante de la gateway, du core et des services relies a la stack locale.",
  },
  {
    to: "/pipeline",
    label: "Live feed",
    title: "Open Logs",
    body: "Suivre les incidents de service et les echanges inter-agent dans une seule console temps reel.",
  },
  {
    to: "/admin",
    label: "Stack map",
    title: "Read Infrastructure",
    body: "Voir les endpoints exposes et les providers declares sans sortir du cockpit.",
  },
];

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
  const statusTone = data.status === "ok" ? "text-[#30d158]" : "text-error";
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

      <section className="scroll-reveal grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(9,14,11,0.9)_26%,rgba(7,7,7,0.95))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">runtime posture</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent font-bold text-accent md:text-5xl">
                {headline(data.status)}
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-[#1d1d1f]/62 md:text-[15px]">
                {narrative(data.status, providers, agents)}
              </p>
              <div className="mt-5 flex flex-wrap items-center gap-2">
                <span className="status-chip border-accent/15 bg-accent/10 text-accent">
                  gateway {data.status === "ok" ? "healthy" : "degraded"}
                </span>
                <span className={["status-chip", data.status === "ok" ? "border-[#e8f5e9] bg-[#f5f5f7]/80 text-[#30d158]" : "border-[#fce4ec] bg-[#f5f5f7]/80 text-error"].join(" ")}>
                  core {isUp ? "online" : "offline"}
                </span>
                <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">
                  providers {providers.length}
                </span>
                {ollamaRuntimeReady ? (
                  <span className="status-chip border-[#e8f5e9] bg-[#f5f5f7]/80 text-[#30d158]">
                    ollama {monitor.data?.ai.ollama.models ?? 0} models
                  </span>
                ) : null}
                <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">
                  agents {agents}
                </span>
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link
                  to="/playground"
                  className="rounded-2xl border border-accent/15 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
                >
                  open playground
                </Link>
                <Link
                  to="/admin"
                  className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#1d1d1f] transition hover:border-accent/15 hover:text-accent"
                >
                  inspect metrics
                </Link>
                <Link
                  to="/pipeline"
                  className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#1d1d1f] transition hover:border-accent/15 hover:text-accent"
                >
                  open logs
                </Link>
                <Button variant="ghost" className="rounded-2xl border border-[rgba(0,0,0,0.08)] px-4 py-2 text-xs uppercase tracking-[0.18em]" onClick={() => void refetch()}>
                  refresh status
                </Button>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">health signal</p>
                <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", statusTone].join(" ")}>
                  {data.status === "ok" ? "nominal" : "degraded"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/48">
                  Gateway and shell alignment for the current routing layer.
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">provider bus</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {providers.length.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/48">
                  Active adapters currently exposed by the core health endpoint.
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">agent registry</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {agents.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/48">
                  Registered agent surfaces ready for inspection or orchestration.
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">dispatch mode</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  local
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/48">
                  Cockpit branche sur la gateway Mascarade et sur le core en amont.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Provider bus" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
          <div className="space-y-5">
            <div>
              <p className="text-sm leading-7 text-[#1d1d1f]/62">
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

            <div className="space-y-3 rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
              <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.18em]">
                <span className="text-muted">signal</span>
                <span className={statusTone}>{data.status === "ok" ? "stable" : "needs attention"}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[#f0f0f2]">
                <div
                  className={[
                    "h-full rounded-full transition-all",
                    data.status === "ok"
                      ? "bg-[linear-gradient(90deg,#30d158,#0071e3)]"
                      : "bg-[linear-gradient(90deg,#ff3b30,#0071e3)]",
                  ].join(" ")}
                  style={{ width: `${Math.max(18, Math.min(100, providers.length * 18 || 22))}%` }}
                />
              </div>
              <p className="text-[12px] leading-5 text-[#1d1d1f]/46">
                Densite calculee a partir du nombre de providers exposes dans le health check courant.
              </p>
            </div>
          </div>
        </Card>
      </section>

      <section className="scroll-reveal grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {actionCards.map((card) => (
          <Link
            key={card.to}
            to={card.to}
            className="group rounded-[1.75rem] border border-[rgba(0,0,0,0.08)] bg-[linear-gradient(180deg,rgba(9,9,9,0.88),rgba(6,7,7,0.98))] p-5 transition duration-200 hover:border-accent/15 hover:bg-[linear-gradient(180deg,rgba(255,209,102,0.06),rgba(8,9,8,0.98))]"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">{card.label}</p>
            <h3 className="mt-3 text-lg font-semibold uppercase tracking-[0.12em] text-accent transition group-hover:font-bold text-accent">
              {card.title}
            </h3>
            <p className="mt-3 text-sm leading-7 text-[#1d1d1f]/54">{card.body}</p>
            <p className="mt-6 text-[11px] uppercase tracking-[0.18em] text-[#aeaeb2] transition group-hover:text-accent">
              enter module
            </p>
          </Link>
        ))}
      </section>

      <section className="scroll-reveal grid gap-4 xl:grid-cols-2">
        <Card
          title="Agent Zero lane"
          className="bg-[linear-gradient(180deg,rgba(255,209,102,0.06),rgba(8,9,8,0.98))]"
        >
          <div className="space-y-4">
            <p className="text-sm leading-7 text-[#1d1d1f]/60">
              Porte d&apos;entree recommandee pour cadrer une demande floue, decomposer une action et basculer
              ensuite vers les lanes specialisees.
            </p>
            <div className="flex flex-wrap gap-2">
              <span className="status-chip border-accent/15 bg-accent/10 text-accent">lead workflow</span>
              <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">intake + triage</span>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Link
                to="/agents/agent-zero"
                className="rounded-[1.4rem] border border-accent/15 bg-[#f5f5f7] px-4 py-4 transition hover:bg-accent/10"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                  open agent zero
                </p>
                <p className="mt-2 text-sm text-[#6e6e73]">/agents/agent-zero</p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/44">
                  Vue detaillee, usages recommandes et acces direct au run lane.
                </p>
              </Link>
              <Link
                to="/orchestrate"
                className="rounded-[1.4rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-4 py-4 transition hover:border-accent/15 hover:bg-[#f5f5f7]"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                  start with zero
                </p>
                <p className="mt-2 text-sm text-[#6e6e73]">guided dispatch lane</p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/44">
                  Lance un cadrage operateur avant de repartir vers les agents specialises.
                </p>
              </Link>
            </div>
          </div>
        </Card>

        <Card title="Dify lane">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-[#1d1d1f]/60">
              Surface builder deja presente dans la stack pour les workflows IA, avec acces web, health API et
              raccourcis logs quand le service derive.
            </p>
            <div className="flex flex-wrap gap-2">
              <span
                className={[
                  "status-chip",
                  difyWeb?.ok
                    ? "border-[#e8f5e9] bg-[#f5f5f7]/80 text-[#30d158]"
                    : "border-[#fce4ec] bg-[#f5f5f7]/80 text-error",
                ].join(" ")}
              >
                dify web {difyWeb?.ok ? "online" : "watch"}
              </span>
              <span
                className={[
                  "status-chip",
                  difyApi?.ok
                    ? "border-[#e8f5e9] bg-[#f5f5f7]/80 text-[#30d158]"
                    : "border-[#fce4ec] bg-[#f5f5f7]/80 text-error",
                ].join(" ")}
              >
                dify api {difyApi?.ok ? "online" : "watch"}
              </span>
              <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">redis + postgres</span>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <a
                href={difyWebHref}
                target="_blank"
                rel="noreferrer"
                className="rounded-[1.4rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-4 py-4 transition hover:border-accent/15 hover:bg-[#f5f5f7]"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                  open dify web
                </p>
                <p className="mt-2 text-sm text-[#6e6e73]">{difyWebHref.replace(/^https?:\/\//, "")}</p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/44">
                  {difyWeb ? `http ${difyWeb.status || "-"} / ${Math.round(difyWeb.latency_ms || 0)} ms` : "surface builder pending"}
                </p>
              </a>
              <a
                href={difyApiHref}
                target="_blank"
                rel="noreferrer"
                className="rounded-[1.4rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-4 py-4 transition hover:border-accent/15 hover:bg-[#f5f5f7]"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                  open dify api
                </p>
                <p className="mt-2 text-sm text-[#6e6e73]">{difyApiHref.replace(/^https?:\/\//, "")}</p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/44">
                  {difyApi ? `http ${difyApi.status || "-"} / ${Math.round(difyApi.latency_ms || 0)} ms` : "workflow api pending"}
                </p>
              </a>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                to="/logs?service=dify-web"
                className="rounded-2xl border border-accent/15 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/10"
              >
                dify web logs
              </Link>
              <Link
                to="/logs?service=dify-api"
                className="rounded-2xl border border-accent/15 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/10"
              >
                dify api logs
              </Link>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
