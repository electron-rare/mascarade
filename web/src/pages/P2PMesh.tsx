import { useFetch } from "../hooks/useFetch";
import { Badge, Card, LoadingPanel } from "../components/ui";

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

function statusColor(ok: boolean) {
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

export default function P2PMesh() {
  const { data: topology, loading: topoLoading, error: topoError } =
    useFetch<TopologyData>("/api/p2p/topology", { pollIntervalMs: 10000 });

  const { data: caps } = useFetch<CapabilitiesData>("/api/p2p/capabilities");

  if (topoLoading && !topology) return <LoadingPanel title="Loading mesh topology" />;
  if (topoError) return <p className="text-error text-sm">{topoError}</p>;

  const mesh = topology?.mesh;
  const peers = topology?.peers || [];
  const localNode = topology?.node;

  return (
    <div className="space-y-6">
      {/* Summary cards */}
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

      {/* Peer table */}
      <Card>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-amber-50/60">Peer Nodes</h2>
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
                    <span className={statusColor(peer.ok)}>{peer.ok ? "UP" : "DOWN"}</span>
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
              {peers.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-4 text-center text-amber-50/40">No peers connected</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Capabilities */}
      {caps && Object.keys(caps.capabilities).length > 0 && (
        <Card>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-amber-50/60">Capabilities Map</h2>
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
