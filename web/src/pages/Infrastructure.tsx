import { useFetch } from "../hooks/useFetch";
import { Card, JsonView, Spinner } from "../components/ui";

export default function Infrastructure() {
  const health = useFetch<Record<string, unknown>>("/health");
  const providers = useFetch<Record<string, unknown>>("/api/agents/providers");

  if (health.loading) return <Spinner className="mx-auto mt-20" />;
  if (health.error)
    return <p className="text-error text-sm text-center mt-20">{health.error}</p>;

  return (
    <div className="space-y-4">
      <Card title="API Health">
        <JsonView data={health.data ?? {}} />
      </Card>
      <Card title="Providers">
        {providers.loading ? (
          <Spinner />
        ) : providers.error ? (
          <p className="text-error text-sm">{providers.error}</p>
        ) : (
          <JsonView data={providers.data ?? {}} />
        )}
      </Card>
    </div>
  );
}

