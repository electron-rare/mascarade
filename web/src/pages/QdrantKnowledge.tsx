import { useMemo, useState } from "react";
import {
  qdrantKnowledgeApi,
  type QdrantCollection,
  type QdrantHealthResponse,
} from "../api/qdrantKnowledge";
import { useFetch } from "../hooks/useFetch";
import { useApi } from "../hooks/useApi";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  InlineNotice,
  JsonView,
  LoadingPanel,
} from "../components/ui";

function formatBytes(bytes?: number): string {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${Math.round((bytes / Math.pow(k, i)) * 100) / 100} ${sizes[i]}`;
}

function formatNumber(num?: number): string {
  if (!num && num !== 0) return "-";
  return num.toLocaleString();
}

function distanceColor(distance?: string): string {
  switch (distance) {
    case "Cosine":
      return "text-accent";
    case "Euclid":
      return "text-[#8cffb7]";
    case "Dot":
      return "text-[#ffa366]";
    default:
      return "text-muted";
  }
}

export default function QdrantKnowledge() {
  const [selected, setSelected] = useState<QdrantCollection | null>(null);

  const healthApi = useFetch<QdrantHealthResponse>("/api/qdrant-knowledge/health", {
    pollIntervalMs: 10000,
  });

  const collectionsApi = useApi<{ collections: QdrantCollection[] }, void>(() =>
    qdrantKnowledgeApi.listCollections(),
  );

  const detailsApi = useApi<{ collection: QdrantCollection }, string>((collectionName) =>
    qdrantKnowledgeApi.getCollection(collectionName),
  );

  const collections = collectionsApi.data?.collections ?? [];
  const totalPoints = collections.reduce((sum, c) => sum + (c.points_count ?? 0), 0);
  const totalVectors = collections.reduce((sum, c) => sum + (c.vectors_count ?? 0), 0);
  const totalDiskSize = collections.reduce((sum, c) => sum + (c.disk_data_size ?? 0), 0);
  const totalRamSize = collections.reduce((sum, c) => sum + (c.ram_data_size ?? 0), 0);
  const healthStatus = healthApi.data?.ok ? "online" : healthApi.error ? "error" : "checking";

  const narrative = useMemo(() => {
    if (healthApi.loading && !healthApi.data) return "Checking Qdrant health status...";
    if (healthApi.error) return "Unable to connect to Qdrant. Check that the service is running.";
    if (collectionsApi.loading) return "Loading collections from Qdrant...";
    if (collections.length === 0) return "No collections found. Create a collection to get started.";
    return `${collections.length} collection(s) available. Select a collection to view details and manage vectors.`;
  }, [healthApi.loading, healthApi.data, healthApi.error, collectionsApi.loading, collections.length]);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(102,209,255,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">qdrant vector store</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                Manage vector collections and knowledge embeddings
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Cette vue permet de surveiller et gerer les collections Qdrant: voir les statistiques, explorer les vecteurs, et verifier la sante du service vectoriel.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span
                  className={`status-chip ${
                    healthStatus === "online"
                      ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"
                      : healthStatus === "error"
                        ? "border-[#5d2332] bg-[#18070d]/80 text-error"
                        : "border-border/80 bg-black/30 text-muted"
                  }`}
                >
                  {healthStatus}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  {collections.length} collections
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  {selected ? "collection selected" : "browse mode"}
                </span>
                {healthApi.data?.version ? (
                  <span className="status-chip border-border/80 bg-black/30 text-muted">
                    v{healthApi.data.version}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">total points</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {formatNumber(totalPoints)}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Nombre total de points indexes dans toutes les collections.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">total vectors</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {formatNumber(totalVectors)}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Nombre total de vecteurs stockes dans Qdrant.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">disk usage</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {formatBytes(totalDiskSize)}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Espace disque utilise pour le stockage vectoriel.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">ram usage</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {formatBytes(totalRamSize)}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Memoire RAM utilisee pour les index vectoriels.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Collection browser" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/58">{narrative}</p>
            <div className="flex gap-3">
              <Button
                onClick={() => void collectionsApi.execute(undefined)}
                loading={collectionsApi.loading}
                disabled={healthStatus === "error"}
              >
                refresh collections
              </Button>
            </div>
            {collectionsApi.error ? (
              <InlineNotice title="collection load error" message={collectionsApi.error} tone="error" />
            ) : null}
            {healthApi.error ? (
              <InlineNotice title="health check error" message={healthApi.error} tone="error" />
            ) : null}
          </div>
        </Card>
      </section>

      {collectionsApi.loading && !collectionsApi.data ? (
        <LoadingPanel message="Loading collections..." />
      ) : collections.length > 0 ? (
        <Card title="Collections">
          <div className="space-y-3">
            {collections.map((collection) => (
              <button
                key={collection.name}
                disabled={detailsApi.loading}
                onClick={async () => {
                  setSelected(collection);
                  await detailsApi.execute(collection.name);
                }}
                className="w-full rounded-[1.5rem] border border-border/80 bg-black/25 p-4 text-left transition hover:border-accent/35 hover:bg-black/35 disabled:opacity-50"
              >
                <div className="flex flex-col gap-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="screen-label">collection</p>
                      <p className="mt-2 text-[14px] font-semibold uppercase tracking-[0.16em] text-accent">
                        {collection.name}
                      </p>
                    </div>
                    <Badge color={selected?.name === collection.name ? "accent" : "muted"}>
                      {selected?.name === collection.name ? "active" : "view"}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">points</p>
                      <p className="mt-1 text-sm font-medium text-amber-100/80">
                        {formatNumber(collection.points_count)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">vectors</p>
                      <p className="mt-1 text-sm font-medium text-amber-100/80">
                        {formatNumber(collection.vectors_count)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">segments</p>
                      <p className="mt-1 text-sm font-medium text-amber-100/80">
                        {formatNumber(collection.segments_count)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">distance</p>
                      <p className={`mt-1 text-sm font-medium ${distanceColor(collection.config?.params?.vectors?.distance)}`}>
                        {collection.config?.params?.vectors?.distance ?? "-"}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3 text-xs text-amber-100/46">
                    <span>disk: {formatBytes(collection.disk_data_size)}</span>
                    <span>•</span>
                    <span>ram: {formatBytes(collection.ram_data_size)}</span>
                    {collection.config?.params?.vectors?.size ? (
                      <>
                        <span>•</span>
                        <span>vector size: {collection.config.params.vectors.size}</span>
                      </>
                    ) : null}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </Card>
      ) : !collectionsApi.loading && !healthApi.loading ? (
        <EmptyState
          message="No collections found. Collections will appear here once created."
          action={
            <Button variant="secondary" onClick={() => void collectionsApi.execute(undefined)}>
              Refresh
            </Button>
          }
        />
      ) : null}

      {selected && detailsApi.data?.collection ? (
        <Card title={`Collection: ${selected.name}`}>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-2xl border border-border/80 bg-black/20 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">points count</p>
                <p className="mt-2 text-xl font-semibold text-accent">
                  {formatNumber(detailsApi.data.collection.points_count)}
                </p>
              </div>
              <div className="rounded-2xl border border-border/80 bg-black/20 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">vectors count</p>
                <p className="mt-2 text-xl font-semibold text-accent">
                  {formatNumber(detailsApi.data.collection.vectors_count)}
                </p>
              </div>
              <div className="rounded-2xl border border-border/80 bg-black/20 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">segments</p>
                <p className="mt-2 text-xl font-semibold text-accent">
                  {formatNumber(detailsApi.data.collection.segments_count)}
                </p>
              </div>
              <div className="rounded-2xl border border-border/80 bg-black/20 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">vector size</p>
                <p className="mt-2 text-xl font-semibold text-accent">
                  {detailsApi.data.collection.config?.params?.vectors?.size ?? "-"}
                </p>
              </div>
            </div>
            <div>
              <p className="mb-2 text-sm font-medium text-amber-100/80">Collection configuration</p>
              <JsonView data={detailsApi.data.collection} />
            </div>
          </div>
        </Card>
      ) : null}

      {detailsApi.error ? (
        <Card title="Error">
          <InlineNotice title="collection details error" message={detailsApi.error} tone="error" />
        </Card>
      ) : null}
    </div>
  );
}
