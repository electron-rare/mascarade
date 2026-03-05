import { useFetch } from "../hooks/useFetch";
import { Card, Spinner } from "../components/ui";

type HealthData = {
  status: string;
  core?: {
    status: string;
    providers?: string[];
    agents?: number;
  };
};

export default function Metrics() {
  const { data, loading, error, refetch } = useFetch<HealthData>("/health");

  if (loading) return <Spinner className="mx-auto mt-20" />;
  if (error)
    return <p className="text-error text-sm text-center mt-20">{error}</p>;
  if (!data) return null;

  const coreOk = data.core?.status === "ok";
  const providers = data.core?.providers ?? [];
  const agents = data.core?.agents ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm text-slate-200 font-semibold">System Monitor</h2>
        <button
          onClick={() => refetch()}
          className="bg-white/5 text-slate-300 border border-border px-3 py-1 rounded text-xs hover:bg-white/10 transition-colors"
        >
          Refresh
        </button>
      </div>

      <Card title="Gateway Health">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div className="rounded border border-border p-3 bg-bg/40">
            <p className="text-muted text-xs uppercase mb-1">API</p>
            <p className={data.status === "ok" ? "text-accent" : "text-error"}>
              {data.status === "ok" ? "ONLINE" : "DOWN"}
            </p>
          </div>
          <div className="rounded border border-border p-3 bg-bg/40">
            <p className="text-muted text-xs uppercase mb-1">Core</p>
            <p className={coreOk ? "text-accent" : "text-error"}>
              {coreOk ? "ONLINE" : "DOWN"}
            </p>
          </div>
          <div className="rounded border border-border p-3 bg-bg/40">
            <p className="text-muted text-xs uppercase mb-1">Agents</p>
            <p className="text-slate-200">{agents}</p>
          </div>
        </div>
      </Card>

      <Card title="Providers">
        {providers.length === 0 ? (
          <p className="text-sm text-muted">No providers reported by core.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {providers.map((provider) => (
              <span
                key={provider}
                className="text-xs px-2 py-1 rounded border border-border bg-white/5 text-slate-200"
              >
                {provider}
              </span>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

