import { useMemo } from "react";
import { useFetch } from "../hooks/useFetch";
import { Badge, Button, Card, InlineNotice, JsonView, LoadingPanel } from "../components/ui";

type DomainScores = {
  kicad?: number;
  spice?: number;
  embedded?: number;
  mixed?: number;
};

type ModelResult = {
  model: string;
  scores: DomainScores;
  overall?: number;
  provider?: string;
};

type BenchmarkMeta = {
  date?: string;
  prompts_count?: number;
  judge_model?: string;
  version?: string;
};

type BenchmarkPayload = {
  results?: ModelResult[];
  metadata?: BenchmarkMeta;
  baseline?: {
    model?: string;
    overall?: number;
  };
};

const DOMAINS = ["kicad", "spice", "embedded", "mixed"] as const;
const BASELINE_MODEL = "phi2-ee";
const BASELINE_SCORE = 3.05;

function scoreTone(score: number | undefined): string {
  if (score === undefined || score === null) return "text-muted";
  if (score >= 7) return "text-[#8cffb7]";
  if (score >= 5) return "text-warning";
  return "text-error";
}

function scoreBg(score: number | undefined): string {
  if (score === undefined || score === null) return "bg-black/20";
  if (score >= 7) return "bg-[#0c170f]/60";
  if (score >= 5) return "bg-[#1a1400]/60";
  return "bg-[#18070d]/60";
}

function scoreBorder(score: number | undefined): string {
  if (score === undefined || score === null) return "border-border/80";
  if (score >= 7) return "border-[#214e31]/60";
  if (score >= 5) return "border-warning/30";
  return "border-[#5d2332]/60";
}

function formatScore(score: number | undefined): string {
  if (score === undefined || score === null) return "--";
  return score.toFixed(2);
}

function computeOverall(scores: DomainScores): number {
  const values = DOMAINS.map((d) => scores[d]).filter(
    (v): v is number => v !== undefined && v !== null,
  );
  if (values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function BarChart({ results }: { results: Array<{ model: string; overall: number }> }) {
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
        const isBaseline = entry.model.toLowerCase() === BASELINE_MODEL.toLowerCase();
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
        x1={labelWidth + (BASELINE_SCORE / maxScore) * chartWidth}
        y1={0}
        x2={labelWidth + (BASELINE_SCORE / maxScore) * chartWidth}
        y2={svgHeight}
        stroke="rgba(255, 100, 100, 0.4)"
        strokeWidth={1}
        strokeDasharray="6 4"
      />
      <text
        x={labelWidth + (BASELINE_SCORE / maxScore) * chartWidth + 4}
        y={svgHeight - 2}
        fill="rgba(255, 100, 100, 0.5)"
        fontSize="9"
        fontFamily="monospace"
      >
        baseline {BASELINE_SCORE}
      </text>
    </svg>
  );
}

export default function Benchmark() {
  const benchFetch = useFetch<BenchmarkPayload>("/api/analytics/v1/benchmarks", {
    pollIntervalMs: 30_000,
  });

  const results = useMemo(() => {
    const raw = benchFetch.data?.results ?? [];
    return raw
      .map((entry) => ({
        ...entry,
        overall: entry.overall ?? computeOverall(entry.scores),
      }))
      .sort((a, b) => b.overall - a.overall);
  }, [benchFetch.data]);

  const meta = benchFetch.data?.metadata;
  const baseline = benchFetch.data?.baseline;
  const baselineOverall = baseline?.overall ?? BASELINE_SCORE;
  const baselineModel = baseline?.model ?? BASELINE_MODEL;
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
                domains {DOMAINS.length}
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
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Total prompts dans la suite de benchmark.
              </p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">judge</p>
              <p className="mt-3 text-lg font-semibold uppercase tracking-[0.12em] text-accent">
                {meta?.judge_model ?? "--"}
              </p>
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Modele utilisee comme juge pour le scoring.
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
                  <th className="px-3 py-3 text-left text-[10px] uppercase tracking-[0.2em] text-muted">
                    rank
                  </th>
                  <th className="px-3 py-3 text-left text-[10px] uppercase tracking-[0.2em] text-muted">
                    model
                  </th>
                  {DOMAINS.map((domain) => (
                    <th
                      key={domain}
                      className="px-3 py-3 text-center text-[10px] uppercase tracking-[0.2em] text-muted"
                    >
                      {domain}
                    </th>
                  ))}
                  <th className="px-3 py-3 text-center text-[10px] uppercase tracking-[0.2em] text-accent">
                    overall
                  </th>
                  <th className="px-3 py-3 text-center text-[10px] uppercase tracking-[0.2em] text-muted">
                    vs baseline
                  </th>
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
                      <td className="px-3 py-3 font-mono text-xs text-muted">
                        {(index + 1).toString().padStart(2, "0")}
                      </td>
                      <td className="px-3 py-3">
                        <span className={["font-semibold uppercase tracking-[0.1em] text-sm", isBaseline ? "text-error" : "text-accent"].join(" ")}>
                          {entry.model}
                        </span>
                        {entry.provider ? (
                          <span className="ml-2 text-[10px] uppercase tracking-[0.14em] text-muted">
                            {entry.provider}
                          </span>
                        ) : null}
                      </td>
                      {DOMAINS.map((domain) => {
                        const score = entry.scores[domain];
                        return (
                          <td
                            key={domain}
                            className={[
                              "px-3 py-3 text-center font-mono text-sm",
                              scoreTone(score),
                              scoreBg(score),
                              scoreBorder(score),
                            ].join(" ")}
                            style={{ borderLeft: `1px solid rgba(255,255,255,0.04)` }}
                          >
                            {formatScore(score)}
                          </td>
                        );
                      })}
                      <td
                        className={[
                          "px-3 py-3 text-center font-mono text-sm font-bold",
                          scoreTone(entry.overall),
                        ].join(" ")}
                      >
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
            <BarChart
              results={results.map((r) => ({ model: r.model, overall: r.overall }))}
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-sm" style={{ backgroundColor: "rgba(140, 255, 183, 0.7)" }} />
              <span className="text-[10px] uppercase tracking-[0.16em] text-muted">score 7+</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-sm" style={{ backgroundColor: "rgba(255, 209, 102, 0.7)" }} />
              <span className="text-[10px] uppercase tracking-[0.16em] text-muted">score 5-7</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-sm" style={{ backgroundColor: "rgba(255, 100, 100, 0.6)" }} />
              <span className="text-[10px] uppercase tracking-[0.16em] text-muted">score &lt;5</span>
            </div>
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
