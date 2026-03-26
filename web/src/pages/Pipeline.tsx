import { useState, useCallback } from "react";
import { useFetch } from "../hooks/useFetch";
import { post } from "../api/client";
import { Badge, Button, Card, InlineNotice, LoadingPanel } from "../components/ui";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type StepStatus = "idle" | "running" | "done" | "failed";

type PipelineStepState = {
  id: string;
  label: string;
  description: string;
  endpoint: string | null;
  buttonLabel: string | null;
  externalUrl?: string;
  status: StepStatus;
  progress_pct: number;
  duration_s: number | null;
  last_run: string | null;
  logs: string[];
};

type PipelineStatusData = {
  steps: PipelineStepState[];
  running: boolean;
};

type PipelineRun = {
  run_id: string;
  started_at: string;
  duration_s: number | null;
  status: StepStatus;
  steps_completed: number;
  steps_total: number;
  models_trained: number;
  benchmark_url?: string;
};

type PipelineRunsData = {
  runs: PipelineRun[];
};

type N8nStatus = {
  ok: boolean;
  version?: string;
  active_workflows?: number;
};

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const DEFAULT_STEPS: PipelineStepState[] = [
  {
    id: "clone",
    label: "Clone Sources",
    description: "Clone Tier 1 repos (27 repos)",
    endpoint: "/api/pipeline/clone",
    buttonLabel: "Run Clone",
    status: "idle",
    progress_pct: 0,
    duration_s: null,
    last_run: null,
    logs: [],
  },
  {
    id: "extract",
    label: "Extract & Convert",
    description: "Extract code → Q&A format",
    endpoint: "/api/pipeline/extract",
    buttonLabel: "Run Extract",
    status: "idle",
    progress_pct: 0,
    duration_s: null,
    last_run: null,
    logs: [],
  },
  {
    id: "quality-check",
    label: "Quality Check",
    description: "LLM judge + dedup + hallucination filter",
    endpoint: "/api/pipeline/quality-check",
    buttonLabel: "Run QC",
    status: "idle",
    progress_pct: 0,
    duration_s: null,
    last_run: null,
    logs: [],
  },
  {
    id: "review",
    label: "Review",
    description: "Human review via Argilla",
    endpoint: null,
    buttonLabel: null,
    externalUrl: "https://argilla.saillant.cc",
    status: "idle",
    progress_pct: 0,
    duration_s: null,
    last_run: null,
    logs: [],
  },
  {
    id: "train",
    label: "Training",
    description: "Fine-tune 28 mini-models (Qwen3-8B QLoRA)",
    endpoint: "/api/pipeline/train",
    buttonLabel: "Start Training",
    status: "idle",
    progress_pct: 0,
    duration_s: null,
    last_run: null,
    logs: [],
  },
  {
    id: "benchmark",
    label: "Benchmark",
    description: "130 prompts x 28 models, Codestral judge",
    endpoint: "/api/pipeline/benchmark",
    buttonLabel: "Run Benchmark",
    status: "idle",
    progress_pct: 0,
    duration_s: null,
    last_run: null,
    logs: [],
  },
  {
    id: "deploy",
    label: "Deploy",
    description: "Import Ollama + deploy photon + publish HF",
    endpoint: "/api/pipeline/deploy",
    buttonLabel: "Deploy",
    status: "idle",
    progress_pct: 0,
    duration_s: null,
    last_run: null,
    logs: [],
  },
];

const N8N_WORKFLOWS = [
  { label: "Clone & Extract", path: "/workflow/clone-extract" },
  { label: "Quality Check", path: "/workflow/quality-check" },
  { label: "Training", path: "/workflow/training" },
  { label: "Benchmark & Deploy", path: "/workflow/benchmark-deploy" },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function statusBadgeColor(status: StepStatus): "accent" | "warning" | "error" | "muted" {
  if (status === "done") return "accent";
  if (status === "running") return "warning";
  if (status === "failed") return "error";
  return "muted";
}

function statusChipClass(status: StepStatus): string {
  if (status === "done") return "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]";
  if (status === "running") return "border-warning/60 bg-warning/20 text-warning animate-pulse";
  if (status === "failed") return "border-[#5d2332] bg-[#18070d]/80 text-error";
  return "border-border/80 bg-black/30 text-muted";
}

function formatDuration(seconds: number | null): string {
  if (!seconds || !Number.isFinite(seconds)) return "--";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatTs(ts: string | null): string {
  if (!ts) return "--";
  try {
    return new Date(ts).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts;
  }
}

/* ------------------------------------------------------------------ */
/*  Pipeline tab content                                               */
/* ------------------------------------------------------------------ */

function PipelineContent() {
  const { data, loading, error, refetch } = useFetch<PipelineStatusData>("/api/pipeline/status", {
    pollIntervalMs: 5_000,
  });

  const steps: PipelineStepState[] = data?.steps ?? DEFAULT_STEPS;
  const pipelineRunning = data?.running ?? false;

  const [runningAction, setRunningAction] = useState<string | null>(null);

  const triggerStep = useCallback(async (stepId: string, endpoint: string) => {
    setRunningAction(stepId);
    try {
      await post(endpoint);
    } catch {
      /* best-effort */
    } finally {
      setRunningAction(null);
      void refetch();
    }
  }, [refetch]);

  const triggerFullPipeline = useCallback(async () => {
    setRunningAction("full");
    try {
      await post("/api/pipeline/run-all");
    } catch {
      /* best-effort */
    } finally {
      setRunningAction(null);
      void refetch();
    }
  }, [refetch]);

  if (loading && !data) {
    return (
      <LoadingPanel
        title="Loading pipeline"
        message="Fetching pipeline status from orchestrator."
      />
    );
  }

  const doneCount = steps.filter((s) => s.status === "done").length;
  const failedCount = steps.filter((s) => s.status === "failed").length;

  return (
    <div className="space-y-6">
      {error ? (
        <InlineNotice title="pipeline note" message={`Refresh failed: ${error}`} tone="error" />
      ) : null}

      {/* Run Full Pipeline header */}
      <Card className="bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(9,14,11,0.9)_26%,rgba(7,7,7,0.95))]">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="screen-label">orchestration</p>
            <h2 className="mt-2 text-2xl font-semibold uppercase tracking-[0.12em] text-accent glow-text">
              Training Pipeline
            </h2>
            <p className="mt-2 text-sm leading-7 text-amber-100/62">
              7-step pipeline: clone, extract, QC, review, train, benchmark, deploy.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className={`status-chip ${pipelineRunning ? statusChipClass("running") : statusChipClass("idle")}`}>
                {pipelineRunning ? "pipeline running" : "pipeline idle"}
              </span>
              <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                {doneCount}/{steps.length} done
              </span>
              {failedCount > 0 ? (
                <span className="status-chip border-[#5d2332] bg-[#18070d]/80 text-error">
                  {failedCount} failed
                </span>
              ) : null}
            </div>
          </div>
          <Button
            variant="primary"
            onClick={triggerFullPipeline}
            disabled={pipelineRunning || runningAction === "full"}
          >
            {runningAction === "full" ? "Starting..." : "Run Full Pipeline"}
          </Button>
        </div>
      </Card>

      {/* Pipeline steps */}
      <div className="space-y-3">
        {steps.map((step, idx) => (
          <Card key={step.id} className="overflow-hidden">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              {/* Left: step info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/80 bg-black/40 text-[11px] font-semibold text-accent">
                    {String(idx + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                      {step.label}
                    </h3>
                    <p className="text-[12px] text-amber-100/54">{step.description}</p>
                  </div>
                </div>

                {/* Status chips */}
                <div className="mt-3 ml-11 flex flex-wrap items-center gap-2">
                  <Badge color={statusBadgeColor(step.status)}>{step.status}</Badge>
                  {step.duration_s != null && step.status === "done" ? (
                    <span className="text-[11px] text-amber-100/50">
                      {formatDuration(step.duration_s)}
                    </span>
                  ) : null}
                  {step.last_run ? (
                    <span className="text-[11px] text-amber-100/40">
                      last: {formatTs(step.last_run)}
                    </span>
                  ) : null}
                </div>

                {/* Progress bar */}
                {step.status === "running" ? (
                  <div className="mt-3 ml-11">
                    <div className="h-2 overflow-hidden rounded-full bg-black/40">
                      <div
                        className="h-full rounded-full bg-[linear-gradient(90deg,#ffd166,#39ff88)] transition-all"
                        style={{ width: `${Math.max(4, step.progress_pct)}%` }}
                      />
                    </div>
                    <p className="mt-1 text-[10px] text-amber-100/40">{step.progress_pct.toFixed(1)}%</p>
                  </div>
                ) : null}

                {/* Logs */}
                {step.logs.length > 0 ? (
                  <div className="mt-3 ml-11 max-h-28 overflow-y-auto rounded-xl border border-border/50 bg-black/40 p-3">
                    {step.logs.slice(-5).map((line, li) => (
                      <p key={li} className="font-mono text-[11px] leading-5 text-amber-100/50">
                        {line}
                      </p>
                    ))}
                  </div>
                ) : null}
              </div>

              {/* Right: action */}
              <div className="shrink-0 lg:mt-1">
                {step.endpoint ? (
                  <Button
                    variant="ghost"
                    onClick={() => triggerStep(step.id, step.endpoint!)}
                    disabled={pipelineRunning || runningAction === step.id}
                  >
                    {runningAction === step.id ? "Running..." : step.buttonLabel}
                  </Button>
                ) : step.externalUrl ? (
                  <a
                    href={step.externalUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
                  >
                    Open Argilla
                  </a>
                ) : null}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Runs tab content                                                   */
/* ------------------------------------------------------------------ */

function RunsContent() {
  const { data, loading, error } = useFetch<PipelineRunsData>("/api/pipeline/runs", {
    pollIntervalMs: 15_000,
  });

  if (loading && !data) {
    return (
      <LoadingPanel
        title="Loading runs"
        message="Fetching pipeline run history."
      />
    );
  }

  if (error && !data) {
    return (
      <InlineNotice title="runs error" message={error} tone="error" className="mx-auto max-w-3xl" />
    );
  }

  const runs = data?.runs ?? [];

  if (runs.length === 0) {
    return (
      <Card>
        <p className="text-center text-sm text-amber-100/50">
          No pipeline runs recorded yet. Launch a full pipeline or individual step to begin.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card title="Pipeline run history">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px]">
            <thead>
              <tr className="border-b border-border/50 text-[10px] uppercase tracking-[0.18em] text-muted">
                <th className="pb-3 pr-4">Run ID</th>
                <th className="pb-3 pr-4">Started</th>
                <th className="pb-3 pr-4">Duration</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 pr-4">Steps</th>
                <th className="pb-3 pr-4">Models</th>
                <th className="pb-3">Benchmark</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.run_id} className="border-b border-border/30">
                  <td className="py-3 pr-4 font-mono text-accent">{run.run_id.slice(0, 8)}</td>
                  <td className="py-3 pr-4 text-amber-100/60">{formatTs(run.started_at)}</td>
                  <td className="py-3 pr-4 text-amber-100/60">{formatDuration(run.duration_s)}</td>
                  <td className="py-3 pr-4">
                    <Badge color={statusBadgeColor(run.status)}>{run.status}</Badge>
                  </td>
                  <td className="py-3 pr-4 text-amber-100/60">
                    {run.steps_completed}/{run.steps_total}
                  </td>
                  <td className="py-3 pr-4 text-amber-100/60">{run.models_trained}</td>
                  <td className="py-3">
                    {run.benchmark_url ? (
                      <a
                        href={run.benchmark_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent hover:underline"
                      >
                        results
                      </a>
                    ) : (
                      <span className="text-amber-100/30">--</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  n8n tab content                                                    */
/* ------------------------------------------------------------------ */

function N8nContent() {
  const { data, loading, error } = useFetch<N8nStatus>("/api/pipeline/n8n-status", {
    pollIntervalMs: 30_000,
  });

  return (
    <div className="space-y-6">
      {/* n8n status */}
      <Card title="n8n status">
        <div className="space-y-4">
          {loading && !data ? (
            <p className="text-sm text-amber-100/50">Checking n8n API...</p>
          ) : error ? (
            <InlineNotice title="n8n unreachable" message={error} tone="error" />
          ) : (
            <div className="flex flex-wrap gap-2">
              <span className={`status-chip ${statusChipClass(data?.ok ? "done" : "failed")}`}>
                n8n {data?.ok ? "online" : "offline"}
              </span>
              {data?.version ? (
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  v{data.version}
                </span>
              ) : null}
              {data?.active_workflows != null ? (
                <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                  {data.active_workflows} active workflows
                </span>
              ) : null}
            </div>
          )}
          <a
            href="https://n8n.saillant.cc"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block rounded-2xl border border-accent/35 bg-accent/10 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
          >
            Open n8n
          </a>
        </div>
      </Card>

      {/* n8n embed */}
      <Card title="n8n interface">
        <div className="overflow-hidden rounded-2xl border border-border/50">
          <iframe
            src="https://n8n.saillant.cc"
            className="h-[600px] w-full border-0 bg-black"
            title="n8n workflow editor"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
          />
        </div>
        <p className="mt-2 text-[11px] text-amber-100/40">
          Si l'iframe ne charge pas (CORS), utilisez le lien direct ci-dessus.
        </p>
      </Card>

      {/* Workflow links */}
      <Card title="Workflow shortcuts">
        <div className="grid gap-3 sm:grid-cols-2">
          {N8N_WORKFLOWS.map((wf) => (
            <a
              key={wf.path}
              href={`https://n8n.saillant.cc${wf.path}`}
              target="_blank"
              rel="noopener noreferrer"
              className="group rounded-[1.4rem] border border-border/80 bg-black/20 p-4 transition hover:border-accent/35"
            >
              <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-accent transition group-hover:glow-text">
                {wf.label}
              </p>
              <p className="mt-1 text-[11px] text-amber-100/50">
                n8n.saillant.cc{wf.path}
              </p>
            </a>
          ))}
        </div>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main export                                                        */
/* ------------------------------------------------------------------ */

const TABS = ["pipeline", "runs", "n8n"] as const;

export default function Pipeline() {
  const [tab, setTab] = useState<string>("pipeline");

  return (
    <div className="space-y-6">
      <div className="flex gap-1 mb-6">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-2xl text-xs uppercase tracking-[0.16em] transition ${
              tab === t
                ? "bg-accent/15 text-accent border border-accent/30"
                : "bg-black/30 text-muted border border-border/50 hover:text-accent"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "pipeline" && <PipelineContent />}
      {tab === "runs" && <RunsContent />}
      {tab === "n8n" && <N8nContent />}
    </div>
  );
}
