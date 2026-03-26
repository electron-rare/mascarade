import { useMemo } from "react";
import { useFetch } from "../hooks/useFetch";
import { Badge, Button, Card, InlineNotice, JsonView, LoadingPanel } from "../components/ui";

type NodeInfo = {
  node_id?: string;
  name?: string;
  ip?: string;
  role?: string;
  status?: "online" | "offline" | "degraded";
  services?: string[];
  cpu_percent?: number;
  ram_percent?: number;
  disk_percent?: number;
  gpu?: {
    model?: string;
    vram_total_gb?: number;
    vram_used_gb?: number;
    utilization_percent?: number;
  };
  last_sync?: string;
  git_commit?: string;
};

type ClusterPayload = {
  nodes?: NodeInfo[];
};

type P2PPeer = {
  node_id?: string;
  name?: string;
  ip?: string;
  status?: string;
};

type P2PPayload = {
  peers?: P2PPeer[];
};

const FLEET_MANIFEST: {
  name: string;
  ip: string;
  role: string;
  services: string[];
  hasGpu: boolean;
}[] = [
  {
    name: "photon",
    ip: "192.168.0.119",
    role: "Prod, core + API Docker",
    services: ["core", "gateway", "ollama", "qdrant", "searxng", "comfyui"],
    hasGpu: false,
  },
  {
    name: "KXKM-AI",
    ip: "100.87.54.119",
    role: "GPU RTX 4090, finetune",
    services: ["ollama", "finetune", "comfyui", "argilla"],
    hasGpu: true,
  },
  {
    name: "Tower",
    ip: "192.168.0.120",
    role: "Argilla, Nextcloud",
    services: ["argilla", "nextcloud", "ollama"],
    hasGpu: false,
  },
  {
    name: "grosmac",
    ip: "local",
    role: "Dev",
    services: ["core", "ollama", "dev-gateway"],
    hasGpu: false,
  },
  {
    name: "Cils",
    ip: "100.126.225.111",
    role: "macOS Intel",
    services: ["ollama"],
    hasGpu: false,
  },
];

function statusTone(status: string | undefined): string {
  if (status === "online") return "text-[#8cffb7]";
  if (status === "degraded") return "text-warning";
  return "text-error";
}

function statusChipTone(status: string | undefined): string {
  if (status === "online") return "border-green-400/60 bg-green-500/20 text-emerald-100";
  if (status === "degraded") return "border-warning/60 bg-warning/20 text-warning";
  return "border-red-400/60 bg-red-500/20 text-red-200";
}

function usageBar(percent: number | undefined): string {
  if (percent === undefined || percent === null) return "bg-border/40";
  if (percent >= 90) return "bg-error";
  if (percent >= 70) return "bg-warning";
  return "bg-[#8cffb7]";
}

function formatPercent(value: number | undefined): string {
  if (value === undefined || value === null) return "--";
  return `${Math.round(value)}%`;
}

function shortCommit(hash: string | undefined): string {
  if (!hash) return "--";
  return hash.substring(0, 7);
}

function formatSync(ts: string | undefined): string {
  if (!ts) return "--";
  try {
    const date = new Date(ts);
    return date.toLocaleString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      day: "2-digit",
      month: "2-digit",
    });
  } catch {
    return ts;
  }
}

export default function Fleet() {
  const cluster = useFetch<ClusterPayload>("/api/cluster/nodes", {
    pollIntervalMs: 15_000,
  });
  const p2p = useFetch<P2PPayload>("/api/p2p", {
    pollIntervalMs: 15_000,
  });

  const apiNodes = cluster.data?.nodes ?? [];
  const p2pPeers = p2p.data?.peers ?? [];

  const machines = useMemo(() => {
    return FLEET_MANIFEST.map((manifest) => {
      const apiNode = apiNodes.find(
        (n) =>
          n.name?.toLowerCase() === manifest.name.toLowerCase() ||
          n.node_id?.toLowerCase() === manifest.name.toLowerCase() ||
          n.ip === manifest.ip,
      );
      const p2pPeer = p2pPeers.find(
        (p) =>
          p.name?.toLowerCase() === manifest.name.toLowerCase() ||
          p.node_id?.toLowerCase() === manifest.name.toLowerCase() ||
          p.ip === manifest.ip,
      );
      return {
        ...manifest,
        status: apiNode?.status ?? (p2pPeer?.status as "online" | "offline" | "degraded" | undefined) ?? undefined,
        cpu_percent: apiNode?.cpu_percent,
        ram_percent: apiNode?.ram_percent,
        disk_percent: apiNode?.disk_percent,
        gpu: apiNode?.gpu,
        last_sync: apiNode?.last_sync,
        git_commit: apiNode?.git_commit,
        liveServices: apiNode?.services ?? manifest.services,
      };
    });
  }, [apiNodes, p2pPeers]);

  const onlineCount = machines.filter((m) => m.status === "online").length;
  const degradedCount = machines.filter((m) => m.status === "degraded").length;

  if (cluster.loading && !cluster.data && !p2p.data) {
    return (
      <LoadingPanel
        title="Loading fleet inventory"
        message="Collecting cluster node status, resource usage and peer discovery."
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="screen-label">fleet control</p>
            <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
              Cluster machines, services and resource allocation
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
              Vue consolidee des 5 machines du cluster: status, services actifs, utilisation CPU/RAM/disque, GPU et derniere synchronisation git.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                machines {machines.length}
              </span>
              <span className="status-chip border-green-400/60 bg-green-500/20 text-emerald-100">
                online {onlineCount}
              </span>
              {degradedCount > 0 ? (
                <span className="status-chip border-warning/60 bg-warning/20 text-warning">
                  degraded {degradedCount}
                </span>
              ) : null}
              <span className="status-chip border-border/80 bg-black/30 text-muted">
                p2p peers {p2pPeers.length}
              </span>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button
                variant="ghost"
                className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]"
                onClick={() => {
                  void cluster.refetch();
                  void p2p.refetch();
                }}
              >
                refresh all
              </Button>
            </div>
          </div>

          <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">fleet size</p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                {machines.length.toString().padStart(2, "0")}
              </p>
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Nombre total de machines dans le manifest fleet.
              </p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">online</p>
              <p className={["mt-3 text-2xl font-semibold uppercase tracking-[0.12em]", onlineCount > 0 ? "text-[#8cffb7]" : "text-error"].join(" ")}>
                {onlineCount.toString().padStart(2, "0")}
              </p>
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Machines actuellement joignables par le cluster.
              </p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">gpu nodes</p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                {machines.filter((m) => m.hasGpu).length.toString().padStart(2, "0")}
              </p>
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Machines equipees GPU pour finetune et inference.
              </p>
            </div>
            <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-muted">total services</p>
              <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                {machines.reduce((acc, m) => acc + m.liveServices.length, 0).toString().padStart(2, "0")}
              </p>
              <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                Services actifs cumules sur l'ensemble du cluster.
              </p>
            </div>
          </div>
        </div>
      </Card>

      {cluster.error ? (
        <InlineNotice
          title="cluster api note"
          message={`Cluster endpoint: ${cluster.error}. Affichage base sur le manifest statique.`}
          tone="info"
        />
      ) : null}

      <Card title="Machine inventory">
        <div className="space-y-4">
          {machines.map((machine) => (
            <div
              key={machine.name}
              className="rounded-[1.5rem] border border-border/80 bg-black/20 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="screen-label">{machine.name}</p>
                  <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                    {machine.ip}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-amber-100/60">{machine.role}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className={`status-chip ${statusChipTone(machine.status)}`}>
                    {machine.status ?? "unknown"}
                  </span>
                  {machine.hasGpu ? (
                    <Badge color="accent">gpu</Badge>
                  ) : null}
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {machine.liveServices.map((service) => (
                  <Badge key={`${machine.name}-${service}`} color="muted">
                    {service}
                  </Badge>
                ))}
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">cpu</p>
                  <p className={["mt-2 text-sm", machine.cpu_percent !== undefined ? statusTone(machine.cpu_percent < 90 ? "online" : "degraded") : "text-amber-100/78"].join(" ")}>
                    {formatPercent(machine.cpu_percent)}
                  </p>
                  {machine.cpu_percent !== undefined ? (
                    <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-border/30">
                      <div
                        className={`h-full rounded-full ${usageBar(machine.cpu_percent)}`}
                        style={{ width: `${Math.min(machine.cpu_percent, 100)}%` }}
                      />
                    </div>
                  ) : null}
                </div>
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">ram</p>
                  <p className={["mt-2 text-sm", machine.ram_percent !== undefined ? statusTone(machine.ram_percent < 90 ? "online" : "degraded") : "text-amber-100/78"].join(" ")}>
                    {formatPercent(machine.ram_percent)}
                  </p>
                  {machine.ram_percent !== undefined ? (
                    <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-border/30">
                      <div
                        className={`h-full rounded-full ${usageBar(machine.ram_percent)}`}
                        style={{ width: `${Math.min(machine.ram_percent, 100)}%` }}
                      />
                    </div>
                  ) : null}
                </div>
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">disk</p>
                  <p className={["mt-2 text-sm", machine.disk_percent !== undefined ? statusTone(machine.disk_percent < 90 ? "online" : "degraded") : "text-amber-100/78"].join(" ")}>
                    {formatPercent(machine.disk_percent)}
                  </p>
                  {machine.disk_percent !== undefined ? (
                    <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-border/30">
                      <div
                        className={`h-full rounded-full ${usageBar(machine.disk_percent)}`}
                        style={{ width: `${Math.min(machine.disk_percent, 100)}%` }}
                      />
                    </div>
                  ) : null}
                </div>
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">git</p>
                  <p className="mt-2 font-mono text-sm text-amber-100/78">
                    {shortCommit(machine.git_commit)}
                  </p>
                </div>
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">last sync</p>
                  <p className="mt-2 text-sm text-amber-100/78">
                    {formatSync(machine.last_sync)}
                  </p>
                </div>
                <div className="rounded-2xl border border-border/80 bg-black/20 px-3 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-muted">actions</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      className="rounded-lg border border-accent/35 bg-accent/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-accent transition hover:bg-accent/20"
                      onClick={() => void cluster.refetch()}
                    >
                      sync
                    </button>
                    <a
                      href={`ssh://${machine.ip !== "local" ? machine.ip : "localhost"}`}
                      className="rounded-lg border border-border/80 bg-black/30 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted transition hover:text-accent"
                    >
                      ssh
                    </a>
                  </div>
                </div>
              </div>

              {machine.hasGpu ? (
                <div className="mt-4 rounded-2xl border border-accent/20 bg-accent/5 p-4">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-accent">gpu info</p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-4">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted">model</p>
                      <p className="mt-1 text-sm font-semibold uppercase tracking-[0.12em] text-accent">
                        {machine.gpu?.model ?? "RTX 4090"}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted">vram total</p>
                      <p className="mt-1 text-sm text-amber-100/78">
                        {machine.gpu?.vram_total_gb ? `${machine.gpu.vram_total_gb} GB` : "24 GB"}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted">vram used</p>
                      <p className="mt-1 text-sm text-amber-100/78">
                        {machine.gpu?.vram_used_gb ? `${machine.gpu.vram_used_gb} GB` : "--"}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.16em] text-muted">utilization</p>
                      <p className="mt-1 text-sm text-amber-100/78">
                        {formatPercent(machine.gpu?.utilization_percent)}
                      </p>
                      {machine.gpu?.utilization_percent !== undefined ? (
                        <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-border/30">
                          <div
                            className={`h-full rounded-full ${usageBar(machine.gpu.utilization_percent)}`}
                            style={{ width: `${Math.min(machine.gpu.utilization_percent, 100)}%` }}
                          />
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </Card>

      <Card title="Raw payloads">
        <div className="space-y-4">
          <div>
            <p className="screen-label">cluster nodes</p>
            <div className="mt-3">
              <JsonView data={cluster.data ?? {}} />
            </div>
          </div>
          <div>
            <p className="screen-label">p2p discovery</p>
            <div className="mt-3">
              <JsonView data={p2p.data ?? {}} />
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
