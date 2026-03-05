import { useEffect } from "react";
import { opsApi, type OpsMonitor } from "../api/ops";
import { useApi } from "../hooks/useApi";
import { Card, Spinner } from "../components/ui";

function statusClass(ok: boolean): string {
  return ok ? "text-accent" : "text-error";
}

function formatLatency(ms: number): string {
  if (!Number.isFinite(ms)) return "-";
  return `${Math.round(ms)}ms`;
}

export default function Metrics() {
  const { execute, data, loading, error } = useApi<OpsMonitor, void>(() =>
    opsApi.monitor(),
  );

  useEffect(() => {
    execute(undefined).catch(() => undefined);
    const t = window.setInterval(() => {
      execute(undefined).catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(t);
  }, [execute]);

  if (loading && !data) return <Spinner className="mx-auto mt-20" />;
  if (error && !data) {
    return <p className="text-error text-sm text-center mt-20">{error}</p>;
  }
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm uppercase tracking-[0.16em] text-accent">ops monitor</h2>
          <p className="text-xs text-muted mt-1">last sync: {new Date(data.timestamp).toLocaleTimeString()}</p>
        </div>
        <button
          onClick={() => execute(undefined)}
          className="bg-white/5 text-accent border border-border px-3 py-1 rounded text-xs hover:bg-white/10 transition-colors uppercase tracking-wide"
        >
          refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Card title="gateway">
          <div className="space-y-1 text-xs">
            <p>
              API: <span className={statusClass(data.gateway.api.ok)}>{data.gateway.api.ok ? "ONLINE" : "DOWN"}</span>
            </p>
            <p>
              CORE: <span className={statusClass(data.gateway.core)}>{data.gateway.core ? "ONLINE" : "DOWN"}</span>
            </p>
          </div>
        </Card>
        <Card title="ollama">
          <div className="space-y-1 text-xs">
            <p>
              status: <span className={statusClass(data.ai.ollama.ok)}>{data.ai.ollama.ok ? "ONLINE" : "DOWN"}</span>
            </p>
            <p>models: <span className="text-accent">{data.ai.ollama.models}</span></p>
            <p>latency: <span className="text-accent">{formatLatency(data.ai.ollama.latency_ms)}</span></p>
          </div>
        </Card>
        <Card title="qdrant">
          <div className="space-y-1 text-xs">
            <p>
              status: <span className={statusClass(data.ai.qdrant.ok)}>{data.ai.qdrant.ok ? "ONLINE" : "DOWN"}</span>
            </p>
            <p>collections: <span className="text-accent">{data.ai.qdrant.collections}</span></p>
            <p>latency: <span className="text-accent">{formatLatency(data.ai.qdrant.latency_ms)}</span></p>
          </div>
        </Card>
        <Card title="services">
          <div className="space-y-1 text-xs">
            <p>total: <span className="text-accent">{data.services.length}</span></p>
            <p>
              up: <span className="text-accent">{data.services.filter((s) => s.ok).length}</span>
            </p>
            <p>
              down: <span className="text-error">{data.services.filter((s) => !s.ok).length}</span>
            </p>
          </div>
        </Card>
      </div>

      <Card title="services health">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted uppercase tracking-wide border-b border-border">
                <th className="text-left py-2">service</th>
                <th className="text-left py-2">status</th>
                <th className="text-left py-2">http</th>
                <th className="text-left py-2">latency</th>
                <th className="text-left py-2">target</th>
              </tr>
            </thead>
            <tbody>
              {data.services.map((svc) => (
                <tr key={svc.name} className="border-b border-border/50">
                  <td className="py-2 text-accent uppercase">{svc.name}</td>
                  <td className={`py-2 ${statusClass(svc.ok)}`}>{svc.ok ? "ONLINE" : "DOWN"}</td>
                  <td className="py-2 text-amber-100/80">{svc.status || "-"}</td>
                  <td className="py-2 text-amber-100/80">{formatLatency(svc.latency_ms)}</td>
                  <td className="py-2 text-muted">{svc.url}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="core metrics">
        {data.core_metrics.ok ? (
          <pre className="text-xs text-amber-100/90 whitespace-pre-wrap">
            {JSON.stringify(data.core_metrics.data ?? {}, null, 2)}
          </pre>
        ) : (
          <p className="text-error text-xs">
            core metrics unavailable ({data.core_metrics.status}) {data.core_metrics.error || ""}
          </p>
        )}
      </Card>
    </div>
  );
}

