import { Link } from "react-router-dom";
import { useFetch } from "../hooks/useFetch";
import { Badge, Button, Card, Spinner } from "../components/ui";

interface HealthData {
  status: string;
  core: { status: string; providers: string[]; agents: number };
}

const actionCards = [
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
    to: "/metrics",
    label: "Ops",
    title: "Check Metrics",
    body: "Confirmer la sante de la gateway, du core et des services relies a la stack locale.",
  },
  {
    to: "/infra",
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

  if (loading) return <Spinner className="mx-auto mt-20" />;
  if (error) {
    return <p className="mt-20 text-center text-sm text-error">{error}</p>;
  }
  if (!data) return null;

  const core = data.core;
  const isUp = typeof core === "object" && core.status === "ok";
  const providers = isUp ? core.providers : [];
  const agents = isUp ? core.agents : 0;
  const statusTone = data.status === "ok" ? "text-[#8cffb7]" : "text-error";

  return (
    <div className="space-y-6">
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
                  to="/metrics"
                  className="rounded-2xl border border-border/80 bg-black/25 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/78 transition hover:border-accent/35 hover:text-accent"
                >
                  inspect metrics
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
                Les providers declares par le core donnent le ton du runtime. Cette section sert de lecture rapide avant d'ouvrir la metrique detaillee.
              </p>
            </div>

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
            </div>

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

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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
    </div>
  );
}
