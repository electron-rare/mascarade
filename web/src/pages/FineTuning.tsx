import { useFetch } from "../hooks/useFetch";
import { Badge, Card, LoadingPanel } from "../components/ui";

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

type LogEntry = { name: string; lines: number; preview: string; size_kb: number };
type LogsData = { logs: LogEntry[] };

function statusBadge(status: string) {
  const colors: Record<string, "accent" | "warning" | "error" | "muted"> = {
    ready: "accent",
    "needs-router": "warning",
    "needs-teacher": "warning",
    completed: "accent",
    failed: "error",
    training: "warning",
    pending: "muted",
  };
  return <Badge color={colors[status] || "muted"}>{status}</Badge>;
}

function formatDate(ts: number) {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}

export default function FineTuning() {
  const { data: registry, loading: regLoading } = useFetch<RegistryData>("/api/finetune/registry", {
    pollIntervalMs: 30000,
  });
  const { data: caps } = useFetch<CapabilitiesData>("/api/finetune/capabilities");
  const { data: logsData } = useFetch<LogsData>("/api/finetune/logs", { pollIntervalMs: 60000 });

  if (regLoading && !registry) return <LoadingPanel title="Loading fine-tuning data" />;

  const models = Object.values(registry?.models || {});
  const datasets = Object.values(registry?.datasets || {});
  const runs = Object.values(registry?.runs || {});
  const agents = caps?.agents || [];
  const stack = caps?.stack;
  const logs = logsData?.logs || [];

  return (
    <div className="space-y-6">
      {/* Agent status grid */}
      <Card>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-amber-50/60">Pipeline Agents</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {agents.map((agent) => (
            <div key={agent.name} className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold">{agent.name}</p>
                {statusBadge(agent.status)}
              </div>
              <p className="mt-1 text-xs text-amber-50/40">{agent.capability}</p>
              {agent.backend && (
                <p className="mt-0.5 text-xs text-accent">{agent.backend}</p>
              )}
              {agent.methods && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {agent.methods.map((m) => (
                    <Badge key={m} color="accent">{m}</Badge>
                  ))}
                </div>
              )}
              {caps?.capabilities[agent.capability] && (
                <p className="mt-0.5 text-xs text-amber-50/30">
                  Node: {caps.capabilities[agent.capability].nodes.join(", ")}
                </p>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <p className="text-xs uppercase tracking-wider text-amber-50/40">Models</p>
          <p className="text-2xl font-bold">{models.length}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-wider text-amber-50/40">Datasets</p>
          <p className="text-2xl font-bold">{datasets.length}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-wider text-amber-50/40">Runs</p>
          <p className="text-2xl font-bold">{runs.length}</p>
        </Card>
      </div>

      {/* Models */}
      <Card>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-amber-50/60">
          Models ({models.length})
        </h2>
        {models.length === 0 ? (
          <p className="text-sm text-amber-50/40">No models registered. Run the Researcher agent to search HuggingFace.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wider text-amber-50/40">
                  <th className="pb-2 pr-4">Model</th>
                  <th className="pb-2 pr-4">Task</th>
                  <th className="pb-2 pr-4">Size</th>
                  <th className="pb-2 pr-4">Downloads</th>
                  <th className="pb-2 pr-4">License</th>
                  <th className="pb-2">Added</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.model_id} className="border-b border-white/5">
                    <td className="py-2 pr-4 font-mono text-xs">{m.model_id}</td>
                    <td className="py-2 pr-4"><Badge color="muted">{m.task}</Badge></td>
                    <td className="py-2 pr-4">{m.size_gb > 0 ? `${m.size_gb}GB` : "-"}</td>
                    <td className="py-2 pr-4">{m.downloads?.toLocaleString() || "-"}</td>
                    <td className="py-2 pr-4 text-xs text-amber-50/50">{m.license || "-"}</td>
                    <td className="py-2 text-xs text-amber-50/40">{formatDate(m.added_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Datasets */}
      <Card>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-amber-50/60">
          Datasets ({datasets.length})
        </h2>
        {datasets.length === 0 ? (
          <p className="text-sm text-amber-50/40">No datasets registered. Run the Documentalist agent to search HuggingFace.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wider text-amber-50/40">
                  <th className="pb-2 pr-4">Dataset</th>
                  <th className="pb-2 pr-4">Domain</th>
                  <th className="pb-2 pr-4">License</th>
                  <th className="pb-2">Added</th>
                </tr>
              </thead>
              <tbody>
                {datasets.map((d) => (
                  <tr key={d.dataset_id} className="border-b border-white/5">
                    <td className="py-2 pr-4 font-mono text-xs">{d.dataset_id}</td>
                    <td className="py-2 pr-4"><Badge color="muted">{d.domain}</Badge></td>
                    <td className="py-2 pr-4 text-xs text-amber-50/50">{d.license || "-"}</td>
                    <td className="py-2 text-xs text-amber-50/40">{formatDate(d.added_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Runs */}
      {runs.length > 0 && (
        <Card>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-amber-50/60">
            Training Runs ({runs.length})
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wider text-amber-50/40">
                  <th className="pb-2 pr-4">Run</th>
                  <th className="pb-2 pr-4">Model</th>
                  <th className="pb-2 pr-4">Method</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2">Started</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id} className="border-b border-white/5">
                    <td className="py-2 pr-4 font-mono text-xs">{r.run_id}</td>
                    <td className="py-2 pr-4 text-xs">{r.base_model}</td>
                    <td className="py-2 pr-4"><Badge color="muted">{r.method}</Badge></td>
                    <td className="py-2 pr-4">{statusBadge(r.status)}</td>
                    <td className="py-2 text-xs text-amber-50/40">{formatDate(r.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Stack info */}
      {stack && (
        <Card>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-amber-50/60">SOTA Stack</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
              <p className="text-xs text-amber-50/40">Framework</p>
              <p className="text-sm font-semibold text-accent">{stack.framework}</p>
            </div>
            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
              <p className="text-xs text-amber-50/40">Alignment</p>
              <div className="mt-1 flex gap-1">
                {stack.alignment.map((m) => <Badge key={m} color="accent">{m}</Badge>)}
              </div>
            </div>
            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
              <p className="text-xs text-amber-50/40">Export</p>
              <p className="text-sm font-semibold">{stack.export}</p>
            </div>
            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
              <p className="text-xs text-amber-50/40">GPU</p>
              <p className="text-sm font-semibold">{stack.gpu}</p>
            </div>
            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
              <p className="text-xs text-amber-50/40">Recommended Model</p>
              <p className="text-sm font-mono">{stack.recommended_model}</p>
            </div>
            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
              <p className="text-xs text-amber-50/40">Recommended Dataset</p>
              <p className="text-sm font-mono">{stack.recommended_dataset}</p>
            </div>
          </div>
        </Card>
      )}

      {/* Pipeline Logs */}
      {logs.length > 0 && (
        <Card>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-amber-50/60">
            Pipeline Logs ({logs.length})
          </h2>
          <div className="space-y-2">
            {logs.map((log) => (
              <div key={log.name} className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
                <div className="flex items-center justify-between">
                  <p className="font-mono text-xs">{log.name}</p>
                  <span className="text-xs text-amber-50/40">{log.lines} lines · {log.size_kb}KB</span>
                </div>
                <pre className="mt-2 max-h-24 overflow-auto text-xs text-amber-50/50 whitespace-pre-wrap">
                  {log.preview}
                </pre>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
