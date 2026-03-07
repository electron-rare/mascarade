import { Link } from "react-router-dom";
import { useFetch } from "../hooks/useFetch";
import { Badge, Button, Card, EmptyState, InlineNotice, LoadingPanel } from "../components/ui";
import type { KillLifeWorkflowSummary } from "../api/killlife";

type WorkflowListResponse = {
  root: string;
  workflows: KillLifeWorkflowSummary[];
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusColor(status: string): "accent" | "warning" | "error" | "muted" {
  if (status === "ready" || status === "success") return "accent";
  if (status === "draft") return "warning";
  if (status === "failed" || status === "archived") return "error";
  return "muted";
}

export default function KillLifeWorkflows() {
  const { data, loading, error, refetch } = useFetch<WorkflowListResponse>("/api/killlife/workflows");

  if (loading && !data) {
    return (
      <LoadingPanel
        title="Loading Kill_LIFE lane"
        message="Collecting the workflow registry, run posture and edit surface."
      />
    );
  }

  if (error && !data) {
    return (
      <InlineNotice
        title="kill_life registry error"
        message={error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  const workflows = data?.workflows ?? [];
  const readyCount = workflows.filter((workflow) => workflow.status === "ready").length;
  const githubCount = workflows.filter((workflow) => workflow.execution_modes.includes("github")).length;
  const localCount = workflows.filter((workflow) => workflow.execution_modes.includes("local")).length;

  return (
    <div className="space-y-6">
      {error ? <InlineNotice title="registry degraded" message={error} tone="error" /> : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">embedded workflow lane</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                Full graphical editor for Kill_LIFE
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Cette lane relie le cockpit Mascarade au moteur de workflow Kill_LIFE: édition directe du graphe, validation locale, dispatch GitHub, lecture des runs et evidence packs.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                  workflows {workflows.length}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  ready {readyCount}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  local {localCount}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  github {githubCount}
                </span>
              </div>
              <p className="mt-5 text-sm leading-7 text-amber-100/52">
                Root Kill_LIFE courant: <span className="text-accent">{data?.root ?? "-"}</span>
              </p>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">editor posture</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  direct edit
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Les workflows JSON canoniques sont modifiés depuis cette lane.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">run modes</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  local + github
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Les mêmes graphes peuvent piloter la machine locale et les dispatchs GitHub allowlistés.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Workflow actions">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/58">
              Ouvre un workflow pour éditer le graphe, relier des nœuds et lancer les lanes existantes de Kill_LIFE sans quitter le cockpit Mascarade.
            </p>
            <Button variant="ghost" className="w-full" onClick={() => void refetch()}>
              refresh registry
            </Button>
          </div>
        </Card>
      </section>

      {workflows.length === 0 ? (
        <EmptyState
          message="Le dossier Kill_LIFE/workflows ne contient encore aucun JSON canonique."
        />
      ) : (
        <section className="grid gap-4 xl:grid-cols-2">
          {workflows.map((workflow) => (
            <Card key={workflow.id} className="border-border/80 bg-[linear-gradient(180deg,rgba(10,12,11,0.9),rgba(6,6,6,0.98))]">
              <div className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="screen-label">{workflow.category}</p>
                    <h3 className="mt-2 text-xl font-semibold uppercase tracking-[0.12em] text-accent">
                      {workflow.title}
                    </h3>
                    <p className="mt-2 text-sm leading-7 text-amber-100/52">
                      {workflow.node_count} nodes / {workflow.edge_count} edges / v{workflow.version}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge color={statusColor(workflow.status)}>{workflow.status}</Badge>
                    {workflow.execution_modes.map((mode) => (
                      <Badge key={mode} color="muted">
                        {mode}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  {workflow.tags.map((tag) => (
                    <span key={tag} className="status-chip border-border/80 bg-black/30 text-muted">
                      {tag}
                    </span>
                  ))}
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted">updated</p>
                    <p className="mt-3 text-sm leading-6 text-amber-100/78">
                      {formatDate(workflow.updated_at)}
                    </p>
                  </div>
                  <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-muted">latest run</p>
                    {workflow.latest_run ? (
                      <div className="mt-3 space-y-1 text-sm leading-6 text-amber-100/78">
                        <p>{workflow.latest_run.mode}</p>
                        <p>{workflow.latest_run.status}</p>
                        <p>{formatDate(workflow.latest_run.finished_at)}</p>
                      </div>
                    ) : (
                      <p className="mt-3 text-sm leading-6 text-amber-100/45">none</p>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Link
                    to={`/kill-life/${workflow.id}`}
                    className="rounded-2xl border border-accent/40 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
                  >
                    open editor
                  </Link>
                </div>
              </div>
            </Card>
          ))}
        </section>
      )}
    </div>
  );
}
