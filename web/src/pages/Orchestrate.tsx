import { useMemo, useState } from "react";
import { agentsApi, type Agent } from "../api/agents";
import { useApi } from "../hooks/useApi";
import { useFetch } from "../hooks/useFetch";
import { Card, Button, Textarea, Spinner } from "../components/ui";

export default function Orchestrate() {
  const { data, loading, error } = useFetch<{ agents: Agent[] }>("/api/agents");
  const [prompt, setPrompt] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  const canRun = prompt.trim().length > 0 && selected.length > 0;
  const runFn = useMemo(
    () => () => agentsApi.orchestrate({ agent_names: selected, prompt }),
    [selected, prompt],
  );
  const { execute, data: result, loading: running, error: runError } = useApi(runFn);

  if (loading) return <Spinner className="mx-auto mt-20" />;
  if (error) return <p className="text-error text-sm text-center mt-20">{error}</p>;

  const agents = data?.agents ?? [];

  return (
    <div className="space-y-4">
      <Card title="Orchestration">
        <div className="space-y-3">
          <p className="text-sm text-muted">
            Select agents and run a multi-agent orchestration through Hono API.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            {agents.map((a) => {
              const active = selected.includes(a.name);
              return (
                <button
                  key={a.name}
                  onClick={() =>
                    setSelected((curr) =>
                      curr.includes(a.name)
                        ? curr.filter((n) => n !== a.name)
                        : [...curr, a.name],
                    )
                  }
                  className={`text-left px-3 py-2 rounded border text-sm transition-colors ${
                    active
                      ? "border-accent/50 bg-accent/10 text-accent"
                      : "border-border bg-white/5 text-slate-300 hover:bg-white/10"
                  }`}
                >
                  {a.name}
                </button>
              );
            })}
          </div>
          <Textarea
            label="Prompt"
            rows={5}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe the task for selected agents..."
          />
          <Button disabled={!canRun} loading={running} onClick={() => execute(undefined)}>
            Run Orchestration
          </Button>
          {runError && <p className="text-error text-sm">{runError}</p>}
        </div>
      </Card>

      {result && (
        <Card title="Results">
          <div className="space-y-3">
            {result.results?.map((row) => (
              <div key={`${row.agent}-${row.step}`} className="rounded border border-border p-3 bg-bg/40">
                <div className="flex items-center justify-between text-xs text-muted mb-2">
                  <span>{row.agent}</span>
                  <span>
                    {row.provider} / {row.model}
                  </span>
                </div>
                <pre className="text-sm whitespace-pre-wrap text-slate-200">{row.content}</pre>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

