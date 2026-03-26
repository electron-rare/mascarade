import { useState, useMemo } from "react";
import { useFetch } from "../hooks/useFetch";
import { Badge, Button, Card, InlineNotice, LoadingPanel } from "../components/ui";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type RegistryData = {
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

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function qualityColor(score: number): "accent" | "warning" | "error" | "muted" {
  if (score >= 7) return "accent";
  if (score >= 5) return "warning";
  if (score > 0) return "error";
  return "muted";
}

function qualityChip(score: number): string {
  if (score >= 7) return "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]";
  if (score >= 5) return "border-warning/35 bg-warning/10 text-warning";
  if (score > 0) return "border-[#5d2332] bg-[#18070d]/80 text-error";
  return "border-border/80 bg-black/25 text-muted";
}

function formatDate(ts: number) {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}

function formatSize(mb: number): string {
  if (!mb || mb <= 0) return "-";
  if (mb >= 1000) return `${(mb / 1000).toFixed(1)} GB`;
  return `${mb.toFixed(0)} MB`;
}

const DOMAINS = [
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

/* ------------------------------------------------------------------ */
/*  Dataset preview                                                   */
/* ------------------------------------------------------------------ */

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
        <Badge color={qualityColor(dataset.quality_score)}>
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
          <p className="mt-1 text-lg font-semibold text-accent">{formatSize(dataset.size_mb)}</p>
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

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function Datasets() {
  const { data: registry, loading: regLoading, error: regError, refetch } = useFetch<RegistryData>(
    "/api/finetune/registry",
    { pollIntervalMs: 30000 },
  );
  const { data: datasetsResp } = useFetch<DatasetsResponse>("/api/datasets", {
    pollIntervalMs: 30000,
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [domainFilter, setDomainFilter] = useState<string>("all");

  /* Merge registry datasets with the /api/datasets response */
  const allDatasets: DatasetMeta[] = useMemo(() => {
    const fromApi = datasetsResp?.datasets ?? [];
    const fromRegistry = Object.values(registry?.datasets ?? {}).map((d) => ({
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

    /* Deduplicate by dataset_id, preferring the /api/datasets version */
    const map = new Map<string, DatasetMeta>();
    for (const d of fromRegistry) map.set(d.dataset_id, d);
    for (const d of fromApi) map.set(d.dataset_id, d);
    return Array.from(map.values());
  }, [registry, datasetsResp]);

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

  if (regLoading && !registry) {
    return (
      <LoadingPanel
        title="Syncing datasets"
        message="Collecting dataset registry and quality metadata."
      />
    );
  }
  if (regError && !registry) {
    return (
      <InlineNotice
        title="dataset error"
        message={regError}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Hero */}
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
              <span className={["status-chip", qualityChip(avgQuality)].join(" ")}>
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
              <Button variant="ghost" onClick={() => void refetch()}>
                refresh
              </Button>
            </div>
          </div>
        </Card>

        {/* Stats */}
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">total datasets</p>
            <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
              {allDatasets.length.toString().padStart(2, "0")}
            </p>
            <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
              Datasets indexes dans le registre local et le pipeline distribue.
            </p>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">total examples</p>
            <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
              {totalRows.toLocaleString()}
            </p>
            <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
              Nombre total d'exemples cumules dans tous les datasets indexes.
            </p>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">avg quality</p>
            <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", avgQuality >= 7 ? "text-[#8cffb7]" : avgQuality >= 5 ? "text-warning" : "text-error"].join(" ")}>
              {avgQuality.toFixed(1)} / 10
            </p>
            <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
              Score moyen de qualite sur l'ensemble du registre.
            </p>
          </div>
          <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted">domains</p>
            <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
              {new Set(allDatasets.map((d) => d.domain)).size}
            </p>
            <p className="mt-2 text-[12px] leading-5 text-amber-100/48">
              Nombre de domaines distincts couverts par les datasets actifs.
            </p>
          </div>
        </div>
      </section>

      {/* Domain filters */}
      <div className="flex flex-wrap gap-2">
        {DOMAINS.map((d) => (
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

      {/* Grid + preview */}
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <Card title={`Datasets (${filtered.length})`}>
          {filtered.length === 0 ? (
            <p className="text-sm text-amber-100/40">
              No datasets match the current filter. Adjust the domain or check the registry.
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
                    <span className={["status-chip text-[9px]", qualityChip(d.quality_score)].join(" ")}>
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
                      <p className="mt-1 text-sm font-semibold text-amber-100/80">{formatSize(d.size_mb)}</p>
                    </div>
                  </div>
                  <p className="mt-2 text-[10px] text-amber-100/30">{formatDate(d.added_at)}</p>
                </button>
              ))}
            </div>
          )}
        </Card>

        <Card title="Dataset preview">
          <DatasetPreview dataset={selectedDataset} />
        </Card>
      </section>

      {/* External links */}
      <section className="grid gap-4 xl:grid-cols-2">
        <Card title="Argilla annotation">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/60">
              Interface de labelling et validation humaine des datasets. Les scores de qualite sont enrichis
              par les annotations Argilla.
            </p>
            <a
              href="https://argilla.saillant.cc"
              target="_blank"
              rel="noreferrer"
              className="inline-flex rounded-[1.4rem] border border-accent/35 bg-black/25 px-4 py-4 transition hover:bg-accent/10"
            >
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                  open argilla
                </p>
                <p className="mt-2 text-sm text-amber-100/72">argilla.saillant.cc</p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/44">
                  Labelling, validation et scoring des datasets de fine-tuning.
                </p>
              </div>
            </a>
          </div>
        </Card>

        <Card title="Nextcloud storage">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/60">
              Stockage centralise des fichiers de datasets bruts. Uploader les nouveaux datasets ici avant
              de les importer dans le pipeline.
            </p>
            <a
              href="https://cloud.saillant.cc"
              target="_blank"
              rel="noreferrer"
              className="inline-flex rounded-[1.4rem] border border-border/80 bg-black/25 px-4 py-4 transition hover:border-accent/35 hover:bg-black/30"
            >
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
                  open nextcloud
                </p>
                <p className="mt-2 text-sm text-amber-100/72">cloud.saillant.cc</p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/44">
                  Upload, organisation et partage des fichiers de datasets bruts.
                </p>
              </div>
            </a>
          </div>
        </Card>
      </section>

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
