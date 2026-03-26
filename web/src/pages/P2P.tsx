import { useMemo } from "react";
import { Badge, Card, InlineNotice, LoadingPanel } from "../components/ui";
import { useFetch } from "../hooks/useFetch";

type UnknownRecord = Record<string, unknown>;

type NodeHealth = {
  url: string | null;
  ok: boolean;
  status: number | null;
  latency_ms: number | null;
  error: string | null;
};

type P2PHealthSummary = {
  generated_at?: string;
  total_nodes?: number;
  healthy_nodes?: number;
  unhealthy_nodes?: number;
  nodes?: unknown[];
};

type PeerInfo = {
  peer_id: string;
  role: string;
  base_url: string;
  ok: boolean;
  status: number;
  latency_ms: number;
  error?: string | null;
  remote_node_id?: string | null;
  remote_label?: string | null;
  providers?: string[] | null;
};

type TopologyData = {
  node: {
    node_id: string;
    role: string;
    label: string;
    providers: string[];
    cluster_enabled: boolean;
  };
  peers: PeerInfo[];
  mesh: { total_peers: number; online: number; offline: number };
};

type CapabilitiesData = {
  capabilities: Record<string, string[]>;
};

function topologyStatusColor(ok: boolean) {
  return ok ? "text-[#8cffb7]" : "text-red-400";
}

function roleBadge(role: string) {
  const colors: Record<string, "accent" | "warning" | "muted"> = {
    bridge: "accent",
    infra: "warning",
    worker: "muted",
    general: "muted",
  };
  return <Badge color={colors[role] || "muted"}>{role}</Badge>;
}

type Palette = {
  border: string;
  background: string;
  text: string;
};

type CapabilityPalette = {
  [key: string]: Palette;
};

const DEFAULT_CAPABILITY_PALETTE: Palette = {
  border: "rgba(255, 209, 102, 0.35)",
  background: "rgba(255, 209, 102, 0.14)",
  text: "rgb(255, 209, 102)",
};

const FINETUNE_CAPABILITY_PALETTE: CapabilityPalette = {
  "ft-research": {
    border: "rgba(127, 95, 255, 0.42)",
    background: "rgba(77, 51, 157, 0.24)",
    text: "rgb(184, 163, 255)",
  },
  "ft-student": {
    border: "rgba(0, 255, 133, 0.4)",
    background: "rgba(0, 96, 55, 0.22)",
    text: "rgb(130, 255, 193)",
  },
  "ft-teacher": {
    border: "rgba(255, 153, 102, 0.4)",
    background: "rgba(125, 64, 16, 0.22)",
    text: "rgb(255, 196, 158)",
  },
  "ft-audit": {
    border: "rgba(255, 133, 133, 0.4)",
    background: "rgba(95, 16, 16, 0.2)",
    text: "rgb(255, 183, 183)",
  },
};

function asRecord(value: unknown): UnknownRecord | null {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as UnknownRecord) : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function asStringList(value: unknown): string[] {
  if (typeof value === "string") {
    return [value];
  }
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((entry): entry is string => typeof entry === "string" && entry.trim().length > 0);
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value.trim());
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function pickNodeId(node: UnknownRecord, fallbackIndex: number): string {
  return (
    asString(node.node_id) ??
    asString(node.id) ??
    asString(node.peer_id) ??
    asString(node.host_id) ??
    asString(node.node_name) ??
    asString(node.name) ??
    `node-${fallbackIndex + 1}`
  );
}

function collectCapabilities(value: unknown): string[] {
  const node = asRecord(value);
  if (!node) {
    return [];
  }

  const capabilities = node.capabilities;
  const finetune = (node as UnknownRecord).finetune;
  const candidates: unknown[] = [capabilities, finetune];

  const normalized = new Set<string>();
  for (const candidate of candidates) {
    const asList = asStringList(candidate);
    if (asList.length > 0) {
      asList.forEach((value) => normalized.add(value.trim().toLowerCase()));
      continue;
    }

    const candidateObj = asRecord(candidate);
    if (!candidateObj) {
      continue;
    }

    for (const [key, entry] of Object.entries(candidateObj)) {
      if (key.toLowerCase().startsWith("ft-") && typeof entry === "string" && entry.trim().length > 0) {
        normalized.add(key.toLowerCase());
      }
      if (key === "finetune") {
        for (const value of asStringList(entry)) {
          normalized.add(value.trim().toLowerCase());
        }
      }
    }
  }

  return [...normalized].sort((a, b) => a.localeCompare(b));
}

function paletteForCapability(capability: string): Palette {
  return FINETUNE_CAPABILITY_PALETTE[capability.toLowerCase()] || {
    ...DEFAULT_CAPABILITY_PALETTE,
    text: DEFAULT_CAPABILITY_PALETTE.text,
  };
}

function CapabilityBadge({ capability }: { capability: string }) {
  const style = paletteForCapability(capability);
  return (
    <span
      className="inline-flex min-h-8 items-center rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em]"
      style={{
        borderColor: style.border,
        backgroundColor: style.background,
        color: style.text,
      }}
    >
      {capability}
    </span>
  );
}

function formatLatency(ms: number | null): string {
  if (!ms || ms <= 0) {
    return "--";
  }
  return `${Math.round(ms)} ms`;
}

function asHealthRows(value: unknown): UnknownRecord[] {
  const payload = asRecord(value);
  if (!payload) {
    return Array.isArray(value) ? value.filter((entry): entry is UnknownRecord => asRecord(entry) !== null) : [];
  }

  if (Array.isArray(payload.nodes)) {
    return payload.nodes.filter((entry): entry is UnknownRecord => asRecord(entry) !== null);
  }

  return [];
}

export default function P2P() {
  const nodesFetch = useFetch<unknown[]>("/api/p2p/nodes", {
    pollIntervalMs: 10_000,
  });
  const healthFetch = useFetch<P2PHealthSummary | unknown[]>("/api/p2p/health", {
    pollIntervalMs: 10_000,
  });
  const healthRows = useMemo(() => asHealthRows(healthFetch.data), [healthFetch.data]);
  const healthSummary = useMemo<P2PHealthSummary | null>(() => {
    if (!healthFetch.data || Array.isArray(healthFetch.data)) {
      return null;
    }
    return healthFetch.data as P2PHealthSummary;
  }, [healthFetch.data]);

  const nodes = useMemo(
    () =>
      (nodesFetch.data ?? []).map((raw, index) => {
        const node = asRecord(raw);
        if (!node) {
          return null;
        }
        const id = pickNodeId(node, index);
        return {
          id,
          node,
          capabilities: collectCapabilities(node),
        };
      }).filter((node): node is { id: string; node: UnknownRecord; capabilities: string[] } => Boolean(node)),
    [nodesFetch.data],
  );

  const healthByNode = useMemo(() => {
    const map = new Map<string, NodeHealth>();
    for (const [index, raw] of healthRows.entries()) {
      const payload = asRecord(raw);
      if (!payload) {
        continue;
      }
      const health = asRecord(payload.health);
      if (!health) {
        continue;
      }

      map.set(
        pickNodeId(payload, index),
        {
          url: asString(health.url),
          ok: health.ok === true,
          status: asNumber(health.status),
          latency_ms: asNumber(health.latency_ms),
          error: asString(health.error),
        },
      );
    }
    return map;
  }, [healthRows]);

  const { data: topology, loading: topoLoading } =
    useFetch<TopologyData>("/api/p2p/topology", { pollIntervalMs: 10_000 });

  const { data: caps } = useFetch<CapabilitiesData>("/api/p2p/capabilities");

  const mesh = topology?.mesh;
  const peers = topology?.peers || [];
  const localNode = topology?.node;

  const hasHealthData = healthByNode.size > 0;

  if (nodesFetch.loading && !nodesFetch.data) {
    return (
      <LoadingPanel
        title="Loading node mesh"
        message="Collecting configured P2P nodes and capabilities."
      />
    );
  }

  if (nodesFetch.error && !nodesFetch.data) {
    return (
      <InlineNotice
        title="node mesh unavailable"
        message={nodesFetch.error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card title="P2P Mesh">
        <p className="text-sm leading-7 text-amber-100/60">
          Vue en rafraîchissement auto (10s) des nœuds P2P, de leurs capacités ft-* et de leur santé.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <span className="status-chip border-accent/35 bg-accent/10 text-accent">nodes {nodes.length}</span>
          <span className="status-chip border-border/80 bg-black/30 text-muted">
            healthy {healthSummary?.healthy_nodes ?? healthRows.filter((entry) => {
              const health = asRecord((asRecord(entry) ?? {}).health);
              return health?.ok === true;
            }).length}/{healthSummary?.total_nodes ?? healthRows.length}
          </span>
          <span className="status-chip border-border/80 bg-black/30 text-muted">checks {healthRows.length}</span>
          {nodesFetch.loading ? <span className="status-chip border-accent/35 bg-accent/10 text-accent">refreshing</span> : null}
          {healthFetch.loading ? <span className="status-chip border-accent/35 bg-accent/10 text-accent">pinging</span> : null}
        </div>
      </Card>

      {nodesFetch.error ? (
        <InlineNotice
          title="node refresh note"
          message={`Refresh warning: ${nodesFetch.error}`}
          tone="info"
        />
      ) : null}
      {healthFetch.error ? (
        <InlineNotice
          title="health refresh note"
          message={`Health warning: ${healthFetch.error}`}
          tone="info"
        />
      ) : null}

      <Card title="Node Capabilities">
        {nodes.length === 0 ? (
          <p className="mt-4 rounded-2xl border border-dashed border-accent/20 bg-accent/5 p-4 text-sm text-amber-100/62">
            Aucune capacité de nœud disponible.
          </p>
        ) : null}
        <div className="mt-4 space-y-4">
          {nodes.map((node) => {
            const health = hasHealthData ? healthByNode.get(node.id) : null;
            return (
              <div
                key={node.id}
                className="rounded-3xl border border-border/80 bg-black/20 p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-[14px] font-semibold uppercase tracking-[0.14em] text-accent">
                    {node.id}
                  </h3>
                  <span
                    className={`status-chip ${health?.ok ? "border-green-400/60 bg-green-500/20 text-emerald-100" : "border-red-400/60 bg-red-500/20 text-red-200"}`}
                  >
                    {health ? (health.ok ? "healthy" : "unhealthy") : "unknown"}
                  </span>
                </div>
                <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted">
                  health: {health ? `${formatLatency(health.latency_ms)} · status ${health.status ?? "n/a"}` : "n/a"}
                  {health?.error ? ` · ${health.error}` : ""}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {node.capabilities.length > 0 ? (
                    node.capabilities.map((capability) => (
                      <CapabilityBadge key={`${node.id}-${capability}`} capability={capability} />
                    ))
                  ) : (
                    <span className="inline-flex min-h-8 items-center rounded-full border border-dashed border-border/60 bg-black/25 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-muted">
                      no finetune capability
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Topology summary */}
      {(topology || topoLoading) && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card>
            <p className="text-xs uppercase tracking-wider text-amber-50/40">Total Peers</p>
            <p className="text-2xl font-bold">{mesh?.total_peers ?? "-"}</p>
          </Card>
          <Card>
            <p className="text-xs uppercase tracking-wider text-amber-50/40">Online</p>
            <p className="text-2xl font-bold text-[#8cffb7]">{mesh?.online ?? "-"}</p>
          </Card>
          <Card>
            <p className="text-xs uppercase tracking-wider text-amber-50/40">Offline</p>
            <p className="text-2xl font-bold text-red-400">{mesh?.offline ?? "-"}</p>
          </Card>
          <Card>
            <p className="text-xs uppercase tracking-wider text-amber-50/40">Local Node</p>
            <p className="text-sm font-mono truncate">{localNode?.label || localNode?.node_id?.slice(0, 12) || "-"}</p>
            <p className="text-xs text-amber-50/40">{localNode?.role}</p>
          </Card>
        </div>
      )}

      {/* Peer table */}
      {peers.length > 0 && (
        <Card title="Peer Nodes">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wider text-amber-50/40">
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4">Label</th>
                  <th className="pb-2 pr-4">Role</th>
                  <th className="pb-2 pr-4">Peer ID</th>
                  <th className="pb-2 pr-4">URL</th>
                  <th className="pb-2 pr-4">Latency</th>
                  <th className="pb-2">Providers</th>
                </tr>
              </thead>
              <tbody>
                {peers.map((peer) => (
                  <tr key={peer.peer_id} className="border-b border-white/5">
                    <td className="py-2 pr-4">
                      <span className={topologyStatusColor(peer.ok)}>{peer.ok ? "UP" : "DOWN"}</span>
                    </td>
                    <td className="py-2 pr-4 font-medium">{peer.remote_label || "-"}</td>
                    <td className="py-2 pr-4">{roleBadge(peer.role)}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-amber-50/50">{peer.peer_id.slice(0, 16)}...</td>
                    <td className="py-2 pr-4 text-xs text-amber-50/50">{peer.base_url?.replace(/^https?:\/\//, "") || "-"}</td>
                    <td className="py-2 pr-4">{peer.latency_ms > 0 ? `${Math.round(peer.latency_ms)}ms` : "-"}</td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-1">
                        {(peer.providers || []).map((p) => (
                          <Badge key={p} color="muted">{p}</Badge>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Capabilities map */}
      {caps && Object.keys(caps.capabilities).length > 0 && (
        <Card title="Capabilities Map">
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {Object.entries(caps.capabilities).map(([cap, peerIds]) => (
              <div key={cap} className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-accent">{cap}</p>
                <p className="mt-1 text-xs text-amber-50/50">{peerIds.length} peer(s)</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
