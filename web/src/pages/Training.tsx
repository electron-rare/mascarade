import { useState, useCallback, useRef, useEffect } from "react";
import { useFetch } from "../hooks/useFetch";
import { post } from "../api/client";
import { Badge, Button, Card, InlineNotice, LoadingPanel } from "../components/ui";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type RegistryData = {
  models: Record<string, {
    model_id: string;
    source: string;
    task: string;
    size_gb: number;
    license: string;
    downloads: number;
    likes: number;
    quality_score: number;
    added_at: number;
  }>;
  datasets: Record<string, {
    dataset_id: string;
    source: string;
    domain: string;
    rows: number;
    license: string;
    quality_score: number;
    added_at: number;
  }>;
  runs: Record<string, {
    run_id: string;
    base_model: string;
    dataset: string;
    method: string;
    node: string;
    status: string;
    metrics: Record<string, unknown>;
    started_at: number;
    completed_at: number | null;
  }>;
};

type CapabilitiesData = {
  capabilities: Record<string, { description: string; nodes: string[] }>;
  agents: { name: string; capability: string; status: string; backend?: string; methods?: string[] }[];
  stack?: {
    framework: string;
    alignment: string[];
    export: string;
    gpu: string;
    recommended_model: string;
    recommended_dataset: string;
  };
};

type TrainingStatus = {
  active: boolean;
  current_run?: string;
  model?: string;
  dataset?: string;
  epoch: number;
  total_epochs: number;
  step: number;
  total_steps: number;
  loss: number;
  loss_history: number[];
  eta_seconds: number;
  started_at: number;
  gpu: {
    vram_used_gb: number;
    vram_total_gb: number;
    utilization_pct: number;
    temperature_c: number;
  };
  logs: string[];
};

type MiniModel = {
  id: string;
  model: string;
  dataset: string;
  examples: number;
  epochs: number;
  duration: string;
  loss: number;
  status: "training" | "done" | "queued" | "failed";
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function statusColor(status: string): "accent" | "warning" | "error" | "muted" {
  const map: Record<string, "accent" | "warning" | "error" | "muted"> = {
    done: "accent",
    completed: "accent",
    training: "warning",
    queued: "muted",
    failed: "error",
    pending: "muted",
  };
  return map[status] || "muted";
}

function chipTone(ok: boolean): string {
  return ok
    ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"
    : "border-[#5d2332] bg-[#18070d]/80 text-error";
}

function formatDuration(seconds: number): string {
  if (!seconds || !Number.isFinite(seconds)) return "-";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function buildMiniModels(registry: RegistryData | null): MiniModel[] {
  if (!registry) return [];
  const runs = Object.values(registry.runs);
  return runs.map((r) => {
    const ds = registry.datasets[r.dataset];
    const duration = r.completed_at && r.started_at
      ? formatDuration(r.completed_at - r.started_at)
      : r.started_at
        ? "running"
        : "-";
    return {
      id: r.run_id,
      model: r.base_model,
      dataset: r.dataset,
      examples: ds?.rows ?? 0,
      epochs: (r.metrics?.epochs as number) ?? 0,
      duration,
      loss: (r.metrics?.final_loss as number) ?? (r.metrics?.loss as number) ?? 0,
      status: r.status as MiniModel["status"],
    };
  });
}

/* ------------------------------------------------------------------ */
/*  Loss curve (inline SVG)                                           */
/* ------------------------------------------------------------------ */

function LossCurve({ points }: { points: number[] }) {
  if (points.length < 2) {
    return (
      <div className="flex h-48 items-center justify-center rounded-3xl border border-border/80 bg-black/25">
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted">awaiting loss data</p>
      </div>
    );
  }

  const width = 480;
  const height = 160;
  const pad = 24;
  const maxLoss = Math.max(...points, 0.01);
  const minLoss = Math.min(...points, 0);
  const range = maxLoss - minLoss || 1;

  const toX = (i: number) => pad + (i / (points.length - 1)) * (width - 2 * pad);
  const toY = (v: number) => pad + (1 - (v - minLoss) / range) * (height - 2 * pad);

  const pathD = points
    .map((v, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(v).toFixed(1)}`)
    .join(" ");

  const areaD = `${pathD} L ${toX(points.length - 1).toFixed(1)} ${height - pad} L ${pad} ${height - pad} Z`;

  return (
    <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
      <p className="mb-3 text-[10px] uppercase tracking-[0.2em] text-muted">loss curve</p>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="lossFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ffd166" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#ffd166" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={pad}
            y1={pad + f * (height - 2 * pad)}
            x2={width - pad}
            y2={pad + f * (height - 2 * pad)}
            stroke="rgba(255,209,102,0.06)"
            strokeWidth="1"
          />
        ))}
        {/* area fill */}
        <path d={areaD} fill="url(#lossFill)" />
        {/* line */}
        <path d={pathD} fill="none" stroke="#ffd166" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        {/* latest point */}
        <circle cx={toX(points.length - 1)} cy={toY(points[points.length - 1])} r="4" fill="#ffd166" />
        {/* axis labels */}
        <text x={pad} y={height - 4} fill="rgba(255,209,102,0.36)" fontSize="9" fontFamily="monospace">
          0
        </text>
        <text x={width - pad} y={height - 4} fill="rgba(255,209,102,0.36)" fontSize="9" fontFamily="monospace" textAnchor="end">
          {points.length}
        </text>
        <text x={pad - 4} y={pad + 4} fill="rgba(255,209,102,0.36)" fontSize="9" fontFamily="monospace" textAnchor="end">
          {maxLoss.toFixed(2)}
        </text>
        <text x={pad - 4} y={height - pad + 4} fill="rgba(255,209,102,0.36)" fontSize="9" fontFamily="monospace" textAnchor="end">
          {minLoss.toFixed(2)}
        </text>
      </svg>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Log viewer                                                        */
/* ------------------------------------------------------------------ */

function LogViewer({ lines }: { lines: string[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [lines]);

  return (
    <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
      <p className="mb-3 text-[10px] uppercase tracking-[0.2em] text-muted">training output</p>
      <div
        ref={containerRef}
        className="max-h-56 overflow-auto font-mono text-[11px] leading-5 text-amber-100/54"
      >
        {lines.length === 0 ? (
          <p className="text-muted">No training output available.</p>
        ) : (
          lines.map((line, i) => (
            <div key={i} className="whitespace-pre-wrap break-all">
              <span className="mr-3 inline-block w-8 text-right text-amber-100/22">{i + 1}</span>
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  GPU panel                                                         */
/* ------------------------------------------------------------------ */

function GpuPanel({ gpu }: { gpu: TrainingStatus["gpu"] | undefined }) {
  const vramUsed = gpu?.vram_used_gb ?? 0;
  const vramTotal = gpu?.vram_total_gb ?? 24;
  const util = gpu?.utilization_pct ?? 0;
  const temp = gpu?.temperature_c ?? 0;
  const vramPct = vramTotal > 0 ? (vramUsed / vramTotal) * 100 : 0;
  const tempOk = temp < 80;

  return (
    <Card title="GPU utilization">
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-muted">vram</p>
            <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
              {vramUsed.toFixed(1)} / {vramTotal.toFixed(0)} GB
            </p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-black/40">
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,#ffd166,#ff9b40)] transition-all"
                style={{ width: `${Math.min(100, vramPct)}%` }}
              />
            </div>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-muted">utilization</p>
            <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
              {util.toFixed(0)}%
            </p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-black/40">
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,#39ff88,#ffd166)] transition-all"
                style={{ width: `${Math.min(100, util)}%` }}
              />
            </div>
          </div>
        </div>
        <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] uppercase tracking-[0.18em] text-muted">temperature</p>
              <p className={["mt-2 text-xl font-semibold uppercase tracking-[0.12em]", tempOk ? "text-[#8cffb7]" : "text-error"].join(" ")}>
                {temp > 0 ? `${temp}C` : "-"}
              </p>
            </div>
            <span className={["status-chip", chipTone(tempOk)].join(" ")}>
              {tempOk ? "nominal" : "hot"}
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Progress bar                                                      */
/* ------------------------------------------------------------------ */

function ProgressBar({ status }: { status: TrainingStatus | null }) {
  if (!status?.active) {
    return (
      <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
        <p className="text-[10px] uppercase tracking-[0.18em] text-muted">training progress</p>
        <p className="mt-3 text-lg font-semibold uppercase tracking-[0.12em] text-muted">idle</p>
      </div>
    );
  }

  const pct = status.total_steps > 0 ? (status.step / status.total_steps) * 100 : 0;
  const eta = formatDuration(status.eta_seconds);

  return (
    <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-[0.18em] text-muted">training progress</p>
          <p className="mt-2 text-lg font-semibold uppercase tracking-[0.12em] text-accent">
            epoch {status.epoch}/{status.total_epochs} — step {status.step}/{status.total_steps}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] uppercase tracking-[0.18em] text-muted">eta</p>
          <p className="mt-2 text-lg font-semibold uppercase tracking-[0.12em] text-accent">{eta}</p>
        </div>
      </div>
      <div className="mt-3 h-3 overflow-hidden rounded-full bg-black/40">
        <div
          className="h-full rounded-full bg-[linear-gradient(90deg,#ffd166,#39ff88)] transition-all"
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
      <div className="mt-2 flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-amber-100/40">
        <span>{pct.toFixed(1)}%</span>
        <span>loss {status.loss.toFixed(4)}</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function Training() {
  const { data: registry, loading: regLoading, error: regError, refetch } = useFetch<RegistryData>(
    "/api/finetune/registry",
    { pollIntervalMs: 15000 },
  );
  const { data: caps } = useFetch<CapabilitiesData>("/api/finetune/capabilities");
  const { data: status } = useFetch<TrainingStatus>("/api/finetune/status", {
    pollIntervalMs: 3000,
  });

  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const handleAction = useCallback(async (action: "start" | "stop" | "pause") => {
    setActionLoading(action);
    try {
      await post(`/api/finetune/${action}`);
      void refetch();
    } catch {
      /* errors shown by polling */
    } finally {
      setActionLoading(null);
    }
  }, [refetch]);

  if (regLoading && !registry) {
    return (
      <LoadingPanel
        title="Syncing training dashboard"
        message="Collecting model registry, training status and GPU telemetry."
      />
    );
  }
  if (regError && !registry) {
    return (
      <InlineNotice
        title="training error"
        message={regError}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  const miniModels = buildMiniModels(registry);
  const agents = caps?.agents ?? [];
  const stack = caps?.stack;
  const isTraining = status?.active ?? false;
  const runsTotal = miniModels.length;
  const runsDone = miniModels.filter((m) => m.status === "done").length;
  const runsFailed = miniModels.filter((m) => m.status === "failed").length;

  return (
    <div className="space-y-6">
      {/* Hero banner */}
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(9,14,11,0.9)_26%,rgba(7,7,7,0.95))]">
          <div className="max-w-3xl">
            <p className="screen-label">training deck</p>
            <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
              {isTraining ? "Training in progress" : "Training idle"}
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/62 md:text-[15px]">
              {isTraining
                ? `Model ${status?.model ?? "-"} training on ${status?.dataset ?? "-"}. Epoch ${status?.epoch ?? 0}/${status?.total_epochs ?? 0}.`
                : `${runsTotal} run(s) registered, ${runsDone} completed, ${runsFailed} failed.`}
            </p>

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <span className={["status-chip", chipTone(isTraining)].join(" ")}>
                gpu {isTraining ? "active" : "idle"}
              </span>
              <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                runs {runsTotal}
              </span>
              <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]">
                done {runsDone}
              </span>
              {runsFailed > 0 && (
                <span className="status-chip border-[#5d2332] bg-[#18070d]/80 text-error">
                  failed {runsFailed}
                </span>
              )}
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <Button
                variant="primary"
                loading={actionLoading === "start"}
                disabled={isTraining}
                onClick={() => void handleAction("start")}
              >
                start training
              </Button>
              <Button
                variant="danger"
                loading={actionLoading === "stop"}
                disabled={!isTraining}
                onClick={() => void handleAction("stop")}
              >
                stop training
              </Button>
              <Button
                variant="secondary"
                loading={actionLoading === "pause"}
                disabled={!isTraining}
                onClick={() => void handleAction("pause")}
              >
                pause
              </Button>
              <Button variant="ghost" onClick={() => void refetch()}>
                refresh
              </Button>
            </div>
          </div>
        </Card>

        {/* Summary stats */}
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">pipeline agents</p>
            <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
              {agents.length.toString().padStart(2, "0")}
            </p>
            <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
              Agents enregistres dans le pipeline de fine-tuning distribue.
            </p>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">framework</p>
            <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
              {stack?.framework ?? "unsloth"}
            </p>
            <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
              Stack de fine-tuning avec export {stack?.export ?? "GGUF"}.
            </p>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">gpu</p>
            <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
              {stack?.gpu ?? "RTX 4090"}
            </p>
            <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
              Hardware cible pour le training distribue du cluster.
            </p>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">current loss</p>
            <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", isTraining ? "text-[#8cffb7]" : "text-muted"].join(" ")}>
              {isTraining ? status!.loss.toFixed(4) : "-"}
            </p>
            <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
              Derniere valeur de loss remontee par le worker actif.
            </p>
          </div>
        </div>
      </section>

      {/* Progress + GPU */}
      <section className="grid gap-4 xl:grid-cols-2">
        <Card title="Training progress">
          <div className="space-y-4">
            <ProgressBar status={status ?? null} />
            <LossCurve points={status?.loss_history ?? []} />
          </div>
        </Card>
        <GpuPanel gpu={status?.gpu} />
      </section>

      {/* Mini-models grid */}
      <Card title={`Model runs (${miniModels.length})`}>
        {miniModels.length === 0 ? (
          <p className="text-sm text-amber-100/40">
            No training runs registered. Start a run or check the fine-tuning registry.
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {miniModels.map((m) => (
              <div
                key={m.id}
                className="rounded-[1.4rem] border border-border/80 bg-black/25 p-4 transition hover:border-accent/35"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="truncate text-xs font-semibold uppercase tracking-[0.14em] text-accent">
                    {m.model.split("/").pop()}
                  </p>
                  <Badge color={statusColor(m.status)}>{m.status}</Badge>
                </div>
                <p className="mt-2 truncate text-[11px] text-amber-100/50" title={m.dataset}>
                  {m.dataset}
                </p>
                <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                  <div>
                    <p className="text-[9px] uppercase tracking-[0.2em] text-muted">examples</p>
                    <p className="mt-1 text-sm font-semibold text-amber-100/80">{m.examples || "-"}</p>
                  </div>
                  <div>
                    <p className="text-[9px] uppercase tracking-[0.2em] text-muted">epochs</p>
                    <p className="mt-1 text-sm font-semibold text-amber-100/80">{m.epochs || "-"}</p>
                  </div>
                  <div>
                    <p className="text-[9px] uppercase tracking-[0.2em] text-muted">loss</p>
                    <p className="mt-1 text-sm font-semibold text-amber-100/80">{m.loss ? m.loss.toFixed(3) : "-"}</p>
                  </div>
                </div>
                <div className="mt-2 flex items-center justify-between text-[10px] text-amber-100/36">
                  <span>{m.duration}</span>
                  <span>{m.id.slice(0, 8)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Log viewer */}
      <Card title="Training logs">
        <LogViewer lines={status?.logs ?? []} />
      </Card>

      {regError ? (
        <InlineNotice
          title="polling note"
          message={`Derniere erreur remontee pendant le polling: ${regError}`}
          tone="error"
        />
      ) : null}
    </div>
  );
}
