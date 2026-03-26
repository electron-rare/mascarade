import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useFetch } from "../hooks/useFetch";
import { post } from "../api/client";
import { Badge, Button, Card, InlineNotice, JsonView, LoadingPanel } from "../components/ui";

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

/* ================================================================== */
/*  Datasets tab content (merged from Datasets.tsx)                    */
/* ================================================================== */

type DsRegistryData = {
  datasets: Record<string, {
    dataset_id: string;
    source: string;
    domain: string;
    rows: number;
    license: string;
    quality_score: number;
    added_at: number;
  }>;
};

type DatasetMeta = {
  dataset_id: string;
  domain: string;
  rows: number;
  size_mb: number;
  quality_score: number;
  examples: { input: string; output: string }[];
  source: string;
  license: string;
  added_at: number;
};

type DatasetsResponse = {
  datasets: DatasetMeta[];
};

function dsQualityColor(score: number): "accent" | "warning" | "error" | "muted" {
  if (score >= 7) return "accent";
  if (score >= 5) return "warning";
  if (score > 0) return "error";
  return "muted";
}

function dsQualityChip(score: number): string {
  if (score >= 7) return "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]";
  if (score >= 5) return "border-warning/35 bg-warning/10 text-warning";
  if (score > 0) return "border-[#5d2332] bg-[#18070d]/80 text-error";
  return "border-border/80 bg-black/25 text-muted";
}

function dsFormatDate(ts: number) {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}

function dsFormatSize(mb: number): string {
  if (!mb || mb <= 0) return "-";
  if (mb >= 1000) return `${(mb / 1000).toFixed(1)} GB`;
  return `${mb.toFixed(0)} MB`;
}

const DS_DOMAINS = [
  "all",
  "spice",
  "kicad",
  "embedded",
  "general",
  "code",
  "instruction",
  "conversation",
  "alignment",
] as const;

function DatasetPreview({ dataset }: { dataset: DatasetMeta | null }) {
  if (!dataset) {
    return (
      <div className="flex h-full items-center justify-center rounded-3xl border border-border/80 bg-black/25 p-6">
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
          select a dataset to preview examples
        </p>
      </div>
    );
  }

  const examples = dataset.examples?.slice(0, 3) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="screen-label">preview</p>
          <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
            {dataset.dataset_id}
          </p>
        </div>
        <Badge color={dsQualityColor(dataset.quality_score)}>
          score {dataset.quality_score.toFixed(1)}
        </Badge>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <div className="rounded-2xl border border-border/80 bg-black/25 p-3 text-center">
          <p className="text-[9px] uppercase tracking-[0.2em] text-muted">rows</p>
          <p className="mt-1 text-lg font-semibold text-accent">{dataset.rows.toLocaleString()}</p>
        </div>
        <div className="rounded-2xl border border-border/80 bg-black/25 p-3 text-center">
          <p className="text-[9px] uppercase tracking-[0.2em] text-muted">size</p>
          <p className="mt-1 text-lg font-semibold text-accent">{dsFormatSize(dataset.size_mb)}</p>
        </div>
        <div className="rounded-2xl border border-border/80 bg-black/25 p-3 text-center">
          <p className="text-[9px] uppercase tracking-[0.2em] text-muted">domain</p>
          <p className="mt-1 text-lg font-semibold text-accent">{dataset.domain}</p>
        </div>
      </div>

      {examples.length > 0 ? (
        <div className="space-y-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-muted">sample examples</p>
          {examples.map((ex, i) => (
            <div key={i} className="rounded-2xl border border-border/80 bg-black/25 p-3">
              <div className="mb-2">
                <span className="text-[9px] uppercase tracking-[0.2em] text-muted">input</span>
                <p className="mt-1 max-h-16 overflow-auto text-[11px] leading-5 text-amber-100/70">
                  {ex.input}
                </p>
              </div>
              <div>
                <span className="text-[9px] uppercase tracking-[0.2em] text-accent">output</span>
                <p className="mt-1 max-h-16 overflow-auto text-[11px] leading-5 text-amber-100/54">
                  {ex.output}
                </p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-border/80 bg-black/25 p-4">
          <p className="text-[11px] text-muted">No sample examples available for this dataset.</p>
        </div>
      )}
    </div>
  );
}

function DatasetsContent() {
  const { data: dsRegistry, loading: dsRegLoading, error: dsRegError, refetch: dsRefetch } = useFetch<DsRegistryData>(
    "/api/finetune/registry",
    { pollIntervalMs: 30000 },
  );
  const { data: datasetsResp } = useFetch<DatasetsResponse>("/api/datasets", {
    pollIntervalMs: 30000,
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [domainFilter, setDomainFilter] = useState<string>("all");

  const allDatasets: DatasetMeta[] = useMemo(() => {
    const fromApi = datasetsResp?.datasets ?? [];
    const fromRegistry = Object.values(dsRegistry?.datasets ?? {}).map((d) => ({
      dataset_id: d.dataset_id,
      domain: d.domain,
      rows: d.rows,
      size_mb: 0,
      quality_score: d.quality_score,
      examples: [],
      source: d.source,
      license: d.license,
      added_at: d.added_at,
    }));

    const map = new Map<string, DatasetMeta>();
    for (const d of fromRegistry) map.set(d.dataset_id, d);
    for (const d of fromApi) map.set(d.dataset_id, d);
    return Array.from(map.values());
  }, [dsRegistry, datasetsResp]);

  const filtered = useMemo(() => {
    if (domainFilter === "all") return allDatasets;
    return allDatasets.filter((d) => d.domain === domainFilter);
  }, [allDatasets, domainFilter]);

  const selectedDataset = useMemo(() => {
    return allDatasets.find((d) => d.dataset_id === selectedId) ?? null;
  }, [allDatasets, selectedId]);

  const avgQuality = useMemo(() => {
    const scored = allDatasets.filter((d) => d.quality_score > 0);
    if (scored.length === 0) return 0;
    return scored.reduce((sum, d) => sum + d.quality_score, 0) / scored.length;
  }, [allDatasets]);

  const totalRows = useMemo(() => allDatasets.reduce((sum, d) => sum + d.rows, 0), [allDatasets]);

  if (dsRegLoading && !dsRegistry) {
    return (
      <LoadingPanel
        title="Syncing datasets"
        message="Collecting dataset registry and quality metadata."
      />
    );
  }
  if (dsRegError && !dsRegistry) {
    return (
      <InlineNotice
        title="dataset error"
        message={dsRegError}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.8fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(9,14,11,0.9)_26%,rgba(7,7,7,0.95))]">
          <div className="max-w-3xl">
            <p className="screen-label">dataset registry</p>
            <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
              {allDatasets.length} datasets indexed
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/62 md:text-[15px]">
              Registre consolide des datasets disponibles pour le fine-tuning. Qualite evaluee par le pipeline
              de validation automatique, exemples consultables en direct.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-2">
              <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                datasets {allDatasets.length}
              </span>
              <span className="status-chip border-border/80 bg-black/30 text-muted">
                total rows {totalRows.toLocaleString()}
              </span>
              <span className={["status-chip", dsQualityChip(avgQuality)].join(" ")}>
                avg quality {avgQuality.toFixed(1)}
              </span>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <a
                href="https://argilla.saillant.cc"
                target="_blank"
                rel="noreferrer"
                className="rounded-2xl border border-accent/40 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
              >
                open argilla
              </a>
              <a
                href="https://cloud.saillant.cc"
                target="_blank"
                rel="noreferrer"
                className="rounded-2xl border border-border/80 bg-black/25 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/78 transition hover:border-accent/35 hover:text-accent"
              >
                upload to nextcloud
              </a>
              <Button variant="ghost" onClick={() => void dsRefetch()}>
                refresh
              </Button>
            </div>
          </div>
        </Card>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">total datasets</p>
            <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
              {allDatasets.length.toString().padStart(2, "0")}
            </p>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">total examples</p>
            <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
              {totalRows.toLocaleString()}
            </p>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">avg quality</p>
            <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", avgQuality >= 7 ? "text-[#8cffb7]" : avgQuality >= 5 ? "text-warning" : "text-error"].join(" ")}>
              {avgQuality.toFixed(1)} / 10
            </p>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">domains</p>
            <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
              {new Set(allDatasets.map((d) => d.domain)).size}
            </p>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-2">
        {DS_DOMAINS.map((d) => (
          <button
            key={d}
            className={[
              "rounded-2xl border px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] transition",
              domainFilter === d
                ? "border-accent/40 bg-accent/10 text-accent"
                : "border-border/80 bg-black/25 text-muted hover:border-accent/35 hover:text-accent",
            ].join(" ")}
            onClick={() => setDomainFilter(d)}
          >
            {d}
          </button>
        ))}
      </div>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <Card title={`Datasets (${filtered.length})`}>
          {filtered.length === 0 ? (
            <p className="text-sm text-amber-100/40">
              No datasets match the current filter.
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((d) => (
                <button
                  key={d.dataset_id}
                  className={[
                    "rounded-[1.4rem] border p-4 text-left transition",
                    selectedId === d.dataset_id
                      ? "border-accent/50 bg-accent/8"
                      : "border-border/80 bg-black/25 hover:border-accent/35",
                  ].join(" ")}
                  onClick={() => setSelectedId(d.dataset_id)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="truncate text-xs font-semibold uppercase tracking-[0.14em] text-accent" title={d.dataset_id}>
                      {d.dataset_id.split("/").pop()}
                    </p>
                    <span className={["status-chip text-[9px]", dsQualityChip(d.quality_score)].join(" ")}>
                      {d.quality_score.toFixed(1)}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    <Badge color="muted">{d.domain}</Badge>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-center">
                    <div>
                      <p className="text-[9px] uppercase tracking-[0.2em] text-muted">examples</p>
                      <p className="mt-1 text-sm font-semibold text-amber-100/80">{d.rows.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-[9px] uppercase tracking-[0.2em] text-muted">size</p>
                      <p className="mt-1 text-sm font-semibold text-amber-100/80">{dsFormatSize(d.size_mb)}</p>
                    </div>
                  </div>
                  <p className="mt-2 text-[10px] text-amber-100/30">{dsFormatDate(d.added_at)}</p>
                </button>
              ))}
            </div>
          )}
        </Card>
        <Card title="Dataset preview">
          <DatasetPreview dataset={selectedDataset} />
        </Card>
      </section>
    </div>
  );
}

/* ================================================================== */
/*  Benchmark tab content (merged from Benchmark.tsx)                  */
/* ================================================================== */

type BmDomainScores = {
  kicad?: number;
  spice?: number;
  embedded?: number;
  mixed?: number;
};

type BmModelResult = {
  model: string;
  scores: BmDomainScores;
  overall?: number;
  provider?: string;
};

type BmBenchmarkMeta = {
  date?: string;
  prompts_count?: number;
  judge_model?: string;
  version?: string;
};

type BmBenchmarkPayload = {
  results?: BmModelResult[];
  metadata?: BmBenchmarkMeta;
  baseline?: {
    model?: string;
    overall?: number;
  };
};

const BM_DOMAINS = ["kicad", "spice", "embedded", "mixed"] as const;
const BM_BASELINE_MODEL = "phi2-ee";
const BM_BASELINE_SCORE = 3.05;

function bmScoreTone(score: number | undefined): string {
  if (score === undefined || score === null) return "text-muted";
  if (score >= 7) return "text-[#8cffb7]";
  if (score >= 5) return "text-warning";
  return "text-error";
}

function bmScoreBg(score: number | undefined): string {
  if (score === undefined || score === null) return "bg-black/20";
  if (score >= 7) return "bg-[#0c170f]/60";
  if (score >= 5) return "bg-[#1a1400]/60";
  return "bg-[#18070d]/60";
}

function bmScoreBorder(score: number | undefined): string {
  if (score === undefined || score === null) return "border-border/80";
  if (score >= 7) return "border-[#214e31]/60";
  if (score >= 5) return "border-warning/30";
  return "border-[#5d2332]/60";
}

function bmFormatScore(score: number | undefined): string {
  if (score === undefined || score === null) return "--";
  return score.toFixed(2);
}

function bmComputeOverall(scores: BmDomainScores): number {
  const values = BM_DOMAINS.map((d) => scores[d]).filter(
    (v): v is number => v !== undefined && v !== null,
  );
  if (values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function BmBarChart({ results }: { results: Array<{ model: string; overall: number }> }) {
  const maxScore = 10;
  const barHeight = 28;
  const labelWidth = 140;
  const chartWidth = 500;
  const gap = 6;
  const svgHeight = results.length * (barHeight + gap) + 10;

  return (
    <svg
      viewBox={`0 0 ${labelWidth + chartWidth + 80} ${svgHeight}`}
      className="w-full"
      style={{ maxHeight: `${Math.max(svgHeight, 100)}px` }}
    >
      {results.map((entry, index) => {
        const y = index * (barHeight + gap) + 5;
        const barWidth = (entry.overall / maxScore) * chartWidth;
        const isBaseline = entry.model.toLowerCase() === BM_BASELINE_MODEL.toLowerCase();
        const fill = entry.overall >= 7
          ? "rgba(140, 255, 183, 0.7)"
          : entry.overall >= 5
            ? "rgba(255, 209, 102, 0.7)"
            : "rgba(255, 100, 100, 0.6)";

        return (
          <g key={entry.model}>
            <text
              x={labelWidth - 8}
              y={y + barHeight / 2 + 4}
              textAnchor="end"
              fill={isBaseline ? "rgba(255, 100, 100, 0.8)" : "rgba(255, 209, 102, 0.7)"}
              fontSize="11"
              fontFamily="monospace"
              fontWeight={isBaseline ? "bold" : "normal"}
              style={{ textTransform: "uppercase", letterSpacing: "0.08em" }}
            >
              {entry.model.length > 16 ? entry.model.substring(0, 16) + ".." : entry.model}
            </text>
            <rect
              x={labelWidth}
              y={y}
              width={Math.max(barWidth, 2)}
              height={barHeight}
              rx={4}
              fill={fill}
              opacity={0.85}
            />
            {isBaseline ? (
              <rect
                x={labelWidth}
                y={y}
                width={Math.max(barWidth, 2)}
                height={barHeight}
                rx={4}
                fill="none"
                stroke="rgba(255, 100, 100, 0.6)"
                strokeWidth={2}
                strokeDasharray="4 3"
              />
            ) : null}
            <text
              x={labelWidth + Math.max(barWidth, 2) + 8}
              y={y + barHeight / 2 + 4}
              fill="rgba(255, 209, 102, 0.6)"
              fontSize="11"
              fontFamily="monospace"
            >
              {entry.overall.toFixed(2)}
            </text>
          </g>
        );
      })}
      <line
        x1={labelWidth + (BM_BASELINE_SCORE / maxScore) * chartWidth}
        y1={0}
        x2={labelWidth + (BM_BASELINE_SCORE / maxScore) * chartWidth}
        y2={svgHeight}
        stroke="rgba(255, 100, 100, 0.4)"
        strokeWidth={1}
        strokeDasharray="6 4"
      />
      <text
        x={labelWidth + (BM_BASELINE_SCORE / maxScore) * chartWidth + 4}
        y={svgHeight - 2}
        fill="rgba(255, 100, 100, 0.5)"
        fontSize="9"
        fontFamily="monospace"
      >
        baseline {BM_BASELINE_SCORE}
      </text>
    </svg>
  );
}

function BenchmarkContent() {
  const benchFetch = useFetch<BmBenchmarkPayload>("/api/analytics/v1/benchmarks", {
    pollIntervalMs: 30_000,
  });

  const results = useMemo(() => {
    const raw = benchFetch.data?.results ?? [];
    return raw
      .map((entry) => ({
        ...entry,
        overall: entry.overall ?? bmComputeOverall(entry.scores),
      }))
      .sort((a, b) => b.overall - a.overall);
  }, [benchFetch.data]);

  const meta = benchFetch.data?.metadata;
  const baseline = benchFetch.data?.baseline;
  const baselineOverall = baseline?.overall ?? BM_BASELINE_SCORE;
  const baselineModel = baseline?.model ?? BM_BASELINE_MODEL;
  const aboveBaseline = results.filter((r) => r.overall > baselineOverall).length;

  if (benchFetch.loading && !benchFetch.data) {
    return (
      <LoadingPanel
        title="Loading benchmark results"
        message="Fetching model scores across kicad, spice, embedded and mixed domains."
      />
    );
  }

  if (benchFetch.error && !benchFetch.data) {
    return (
      <InlineNotice
        title="benchmark data unavailable"
        message={benchFetch.error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="screen-label">benchmark lab</p>
            <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
              Model evaluation scores across technical domains
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
              Resultats de benchmark par modele sur les domaines kicad, spice, embedded et mixed. Score global moyen, comparaison avec le baseline HuggingFace ({baselineModel}: {baselineOverall}).
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                models {results.length}
              </span>
              <span className="status-chip border-green-400/60 bg-green-500/20 text-emerald-100">
                above baseline {aboveBaseline}
              </span>
              <span className="status-chip border-border/80 bg-black/30 text-muted">
                domains {BM_DOMAINS.length}
              </span>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button
                variant="ghost"
                className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]"
                onClick={() => void benchFetch.refetch()}
              >
                refresh
              </Button>
            </div>
          </div>

          <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">best model</p>
              <p className="mt-3 text-lg font-semibold uppercase tracking-[0.12em] text-accent">
                {results[0]?.model ?? "--"}
              </p>
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Score: {results[0] ? results[0].overall.toFixed(2) : "--"}
              </p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">baseline</p>
              <p className="mt-3 text-lg font-semibold uppercase tracking-[0.12em] text-error">
                {baselineModel}
              </p>
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Score: {baselineOverall.toFixed(2)}
              </p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">prompts</p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                {meta?.prompts_count?.toString().padStart(2, "0") ?? "--"}
              </p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">judge</p>
              <p className="mt-3 text-lg font-semibold uppercase tracking-[0.12em] text-accent">
                {meta?.judge_model ?? "--"}
              </p>
            </div>
          </div>
        </div>
      </Card>

      {meta ? (
        <Card title="Benchmark metadata">
          <div className="flex flex-wrap gap-2">
            {meta.date ? <Badge color="accent">date: {meta.date}</Badge> : null}
            {meta.prompts_count ? <Badge color="accent">prompts: {meta.prompts_count}</Badge> : null}
            {meta.judge_model ? <Badge color="accent">judge: {meta.judge_model}</Badge> : null}
            {meta.version ? <Badge color="muted">version: {meta.version}</Badge> : null}
          </div>
        </Card>
      ) : null}

      <Card title="Score table">
        {results.length === 0 ? (
          <InlineNotice
            title="no benchmark data"
            message="Aucun resultat de benchmark disponible. Lancez un run depuis la pipeline finetune."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  <th className="px-3 py-3 text-left text-[10px] uppercase tracking-[0.2em] text-muted">rank</th>
                  <th className="px-3 py-3 text-left text-[10px] uppercase tracking-[0.2em] text-muted">model</th>
                  {BM_DOMAINS.map((domain) => (
                    <th key={domain} className="px-3 py-3 text-center text-[10px] uppercase tracking-[0.2em] text-muted">{domain}</th>
                  ))}
                  <th className="px-3 py-3 text-center text-[10px] uppercase tracking-[0.2em] text-accent">overall</th>
                  <th className="px-3 py-3 text-center text-[10px] uppercase tracking-[0.2em] text-muted">vs baseline</th>
                </tr>
              </thead>
              <tbody>
                {results.map((entry, index) => {
                  const isBaseline = entry.model.toLowerCase() === baselineModel.toLowerCase();
                  const delta = entry.overall - baselineOverall;
                  return (
                    <tr
                      key={entry.model}
                      className={[
                        "border-t border-border/40 transition hover:bg-accent/5",
                        isBaseline ? "bg-error/5" : "",
                      ].join(" ")}
                    >
                      <td className="px-3 py-3 font-mono text-xs text-muted">{(index + 1).toString().padStart(2, "0")}</td>
                      <td className="px-3 py-3">
                        <span className={["font-semibold uppercase tracking-[0.1em] text-sm", isBaseline ? "text-error" : "text-accent"].join(" ")}>
                          {entry.model}
                        </span>
                        {entry.provider ? (
                          <span className="ml-2 text-[10px] uppercase tracking-[0.14em] text-muted">{entry.provider}</span>
                        ) : null}
                      </td>
                      {BM_DOMAINS.map((domain) => {
                        const score = entry.scores[domain];
                        return (
                          <td
                            key={domain}
                            className={[
                              "px-3 py-3 text-center font-mono text-sm",
                              bmScoreTone(score),
                              bmScoreBg(score),
                              bmScoreBorder(score),
                            ].join(" ")}
                            style={{ borderLeft: `1px solid rgba(255,255,255,0.04)` }}
                          >
                            {bmFormatScore(score)}
                          </td>
                        );
                      })}
                      <td className={["px-3 py-3 text-center font-mono text-sm font-bold", bmScoreTone(entry.overall)].join(" ")}>
                        {entry.overall.toFixed(2)}
                      </td>
                      <td className="px-3 py-3 text-center font-mono text-sm">
                        <span className={delta >= 0 ? "text-[#8cffb7]" : "text-error"}>
                          {delta >= 0 ? "+" : ""}{delta.toFixed(2)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {results.length > 0 ? (
        <Card title="Score distribution">
          <p className="mb-4 text-sm leading-7 text-amber-100/60">
            Scores globaux par modele. La ligne pointillee rouge indique le baseline {baselineModel} ({baselineOverall}).
          </p>
          <div className="overflow-x-auto rounded-2xl border border-border/80 bg-black/20 p-4">
            <BmBarChart
              results={results.map((r) => ({ model: r.model, overall: r.overall }))}
            />
          </div>
        </Card>
      ) : null}

      <Card title="Raw payload">
        <div>
          <p className="screen-label">benchmarks</p>
          <div className="mt-3">
            <JsonView data={benchFetch.data ?? {}} />
          </div>
        </div>
      </Card>
    </div>
  );
}

/* ================================================================== */
/*  Training content (original)                                        */
/* ================================================================== */

function TrainingContent() {
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

/* ================================================================== */
/*  Main export with tabs                                              */
/* ================================================================== */

const TABS = ["training", "datasets", "benchmark"] as const;

export default function Training() {
  const [tab, setTab] = useState<string>("training");

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
      {tab === "training" && <TrainingContent />}
      {tab === "datasets" && <DatasetsContent />}
      {tab === "benchmark" && <BenchmarkContent />}
    </div>
  );
}
