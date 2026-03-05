import { Link } from "react-router-dom";
import { useFetch } from "../hooks/useFetch";
import { StatCard, Badge, Spinner, Card } from "../components/ui";

interface HealthData {
  status: string;
  core: { status: string; providers: string[]; agents: number };
}

export default function Dashboard() {
  const { data, loading, error } = useFetch<HealthData>("/health");

  if (loading) return <Spinner className="mx-auto mt-20" />;
  if (error)
    return <p className="text-error text-sm text-center mt-20">{error}</p>;
  if (!data) return null;

  const core = data.core;
  const isUp = typeof core === "object" && core.status === "ok";

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="System Status"
          value={data.status === "ok" ? "Healthy" : "Degraded"}
          sub={data.status === "ok" ? "All systems operational" : "Issues detected"}
        />
        <StatCard
          label="Core"
          value={isUp ? "Online" : "Offline"}
          sub={isUp ? "Connected" : "Unreachable"}
        />
        <StatCard
          label="Providers"
          value={isUp ? core.providers.length : "—"}
          sub={isUp ? core.providers.join(", ") : ""}
        />
        <StatCard
          label="Agents"
          value={isUp ? core.agents : "—"}
          sub="Registered agents"
        />
      </div>

      {isUp && (
        <Card title="Providers">
          <div className="flex flex-wrap gap-2">
            {core.providers.map((p: string) => (
              <Badge key={p} color="accent">
                {p}
              </Badge>
            ))}
          </div>
        </Card>
      )}

      <Card title="Quick Actions">
        <div className="flex flex-wrap gap-2">
          <Link
            to="/playground"
            className="bg-accent/10 text-accent border border-accent/30 px-3 py-1.5 rounded text-sm hover:bg-accent/20 transition-colors"
          >
            Open Playground
          </Link>
          <Link
            to="/agents"
            className="bg-white/5 text-slate-300 border border-border px-3 py-1.5 rounded text-sm hover:bg-white/10 transition-colors"
          >
            View Agents
          </Link>
          <Link
            to="/metrics"
            className="bg-white/5 text-slate-300 border border-border px-3 py-1.5 rounded text-sm hover:bg-white/10 transition-colors"
          >
            View Metrics
          </Link>
        </div>
      </Card>
    </div>
  );
}
