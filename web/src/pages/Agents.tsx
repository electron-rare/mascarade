import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { agentsApi, Agent } from "../api/agents";
import { useApi } from "../hooks/useApi";
import { useFetch } from "../hooks/useFetch";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  InlineNotice,
  Input,
  LoadingPanel,
  Modal,
  Select,
  Textarea,
} from "../components/ui";

interface AgentMetrics {
  total_requests: number;
  total_tokens?: number;
  total_cost?: number;
  avg_response_time?: number;
  error_rate?: number;
  last_used: string | null;
}

const strategyOptions = [
  { value: "routellm", label: "RouteLLM" },
  { value: "best", label: "Best" },
  { value: "fastest", label: "Fastest" },
  { value: "cheapest", label: "Cheapest" },
  { value: "specific", label: "Specific" },
];

const routingPolicyOptions = [
  { value: "auto", label: "Auto" },
  { value: "strong", label: "Strong" },
  { value: "cheap", label: "Cheap" },
  { value: "fast", label: "Fast" },
];

function normalizeOptional(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function formatLastUsed(isoString: string | null): string {
  if (!isoString) return "never used";
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  } catch {
    return "unknown";
  }
}

export default function Agents() {
  const { data, loading, error, refetch } = useFetch<{ agents: Agent[] }>("/api/agents");
  const [showCreate, setShowCreate] = useState(false);
  const [createdName, setCreatedName] = useState("");
  const [metricsMap, setMetricsMap] = useState<Record<string, AgentMetrics>>({});
  const [form, setForm] = useState({
    name: "",
    description: "",
    system_prompt: "",
    preferred_provider: "",
    preferred_model: "",
    preferred_role: "",
    strategy: "routellm",
    routing_policy: "auto",
    temperature: 0.7,
    max_tokens: 4096,
  });

  const {
    execute: create,
    loading: creating,
    error: createError,
    status: createStatus,
  } = useApi(() =>
    agentsApi.create({
      name: form.name.trim(),
      description: form.description,
      system_prompt: form.system_prompt,
      preferred_provider: normalizeOptional(form.preferred_provider),
      preferred_model: normalizeOptional(form.preferred_model),
      preferred_role: normalizeOptional(form.preferred_role),
      strategy: form.strategy,
      routing_policy: form.routing_policy,
      temperature: form.temperature,
      max_tokens: form.max_tokens,
    }),
  );

  useEffect(() => {
    if (data?.agents) {
      Promise.all(
        data.agents.map(async (agent) => {
          try {
            const metrics = (await agentsApi.metrics(agent.name)) as unknown as AgentMetrics;
            return { name: agent.name, metrics };
          } catch {
            return {
              name: agent.name,
              metrics: { total_requests: 0, last_used: null } as AgentMetrics,
            };
          }
        }),
      )
        .then((results) => {
          const map: Record<string, AgentMetrics> = {};
          for (const result of results) {
            map[result.name] = result.metrics;
          }
          setMetricsMap(map);
        })
        .catch(() => {
          // Silently ignore metrics fetch errors
        });
    }
  }, [data]);

  const handleCreate = async () => {
    if (!form.name || !form.system_prompt) return;
    const currentName = form.name;
    const created = await create(undefined);
    if (!created) {
      return;
    }
    setCreatedName(currentName);
    setShowCreate(false);
    setForm({
      name: "",
      description: "",
      system_prompt: "",
      preferred_provider: "",
      preferred_model: "",
      preferred_role: "",
      strategy: "routellm",
      routing_policy: "auto",
      temperature: 0.7,
      max_tokens: 4096,
    });
    void refetch();
  };

  if (loading && !data) {
    return (
      <LoadingPanel
        title="Loading registry"
        message="Collecting the agent inventory from the gateway."
      />
    );
  }
  if (error && !data) {
    return (
      <InlineNotice
        title="registry error"
        message={error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  const agents = data?.agents || [];
  const agentZero = agents.find((agent) => agent.name === "agent-zero");
  const sortedAgents = [...agents].sort((left, right) => {
    if (left.name === "agent-zero") return -1;
    if (right.name === "agent-zero") return 1;
    return left.name.localeCompare(right.name);
  });

  return (
    <div className="space-y-6">
      {createStatus === "success" && createdName ? (
        <InlineNotice
          title="agent created"
          message={`Registry updated with ${createdName}. The lane can now be opened from the grid below.`}
          tone="success"
        />
      ) : null}
      {error ? (
        <InlineNotice
          title="registry note"
          message={`Last refresh failed: ${error}`}
          tone="error"
        />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.8fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">agent registry</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                Registry and dispatch surfaces
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Chaque agent expose une surface specialisee. Cette vue sert a lire rapidement
                l&apos;inventaire, verifier la densite du registre et ouvrir un agent en detail.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                  agents {agents.length}
                </span>
                <span className="status-chip border-border/80 bg-black/25 text-muted">
                  create {showCreate ? "open" : "ready"}
                </span>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">registry size</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {agents.length.toString().padStart(2, "0")}
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">creation lane</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  live
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Registry Controls">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/58">
              Ouvrir un agent pour le test detaille ou creer une nouvelle surface specialisee.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => setShowCreate(true)}>new agent</Button>
              <Button variant="secondary" onClick={() => void refetch()}>
                refresh registry
              </Button>
            </div>
          </div>
        </Card>
      </section>

      {agentZero ? (
        <Card className="border-accent/30 bg-[linear-gradient(135deg,rgba(255,209,102,0.10),rgba(8,12,10,0.94)_30%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">lead agent</p>
              <h3 className="mt-3 text-2xl font-semibold uppercase tracking-[0.14em] text-accent glow-text">
                agent-zero
              </h3>
              <p className="mt-3 text-sm leading-7 text-amber-100/62">
                {agentZero.description}
              </p>
              <p className="mt-3 text-[12px] leading-6 text-amber-100/46">
                Utilise-le comme point d&apos;entree quand la demande est encore floue ou quand il faut cadrer, decomposer et prioriser avant d&apos;ouvrir une lane specialisee.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Badge color="accent">recommended first pass</Badge>
              <Link
                to="/agents/agent-zero"
                className="rounded-2xl border border-accent/40 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent transition hover:bg-accent/15"
              >
                open agent-zero
              </Link>
            </div>
          </div>
        </Card>
      ) : null}

      {sortedAgents.length === 0 ? (
        <EmptyState
          message="No agents registered yet."
          action={<Button onClick={() => setShowCreate(true)}>create one</Button>}
        />
      ) : (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {sortedAgents.map((a) => {
            const metrics = metricsMap[a.name];
            return (
              <Link key={a.name} to={`/agents/${a.name}`}>
                <Card className="h-full cursor-pointer transition-colors hover:border-accent/35">
                  <div className="space-y-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="screen-label">agent</p>
                        <h3 className="mt-3 text-lg font-semibold uppercase tracking-[0.12em] text-accent">
                          {a.name}
                        </h3>
                      </div>
                      <Badge color={a.name === "agent-zero" ? "accent" : "accent"}>
                        {a.name === "agent-zero" ? "lead" : "ready"}
                      </Badge>
                    </div>
                    {a.builtin ? (
                      <p className="text-[11px] uppercase tracking-[0.18em] text-amber-100/34">
                        built-in registry entry
                      </p>
                    ) : (
                      <p className="text-[11px] uppercase tracking-[0.18em] text-[#82ffc1]">
                        dynamic editable agent
                      </p>
                    )}
                    <p className="text-sm leading-7 text-amber-100/56">
                      {a.description || "No description provided for this registry entry."}
                    </p>
                    {metrics ? (
                      <div className="flex gap-3 rounded-2xl border border-border/60 bg-black/25 p-3">
                        <div className="flex-1">
                          <p className="text-[10px] uppercase tracking-[0.2em] text-muted">requests</p>
                          <p className="mt-1 text-lg font-semibold text-accent">
                            {metrics.total_requests || 0}
                          </p>
                        </div>
                        <div className="flex-1">
                          <p className="text-[10px] uppercase tracking-[0.2em] text-muted">last used</p>
                          <p className="mt-1 text-xs text-amber-100/70">
                            {formatLastUsed(metrics.last_used)}
                          </p>
                        </div>
                      </div>
                    ) : null}
                    <div className="flex flex-wrap gap-2">
                      {a.preferred_role ? <Badge color="warning">role {a.preferred_role}</Badge> : null}
                      {a.preferred_provider ? (
                        <Badge color="muted">{a.preferred_provider}</Badge>
                      ) : null}
                      {a.preferred_model ? (
                        <Badge color="muted">{a.preferred_model}</Badge>
                      ) : null}
                      {a.strategy ? <Badge color="muted">{a.strategy}</Badge> : null}
                    </div>
                    {a.name === "agent-zero" ? (
                      <p className="text-[11px] uppercase tracking-[0.18em] text-accent">
                        primary intake lane
                      </p>
                    ) : null}
                    <p className="text-[11px] uppercase tracking-[0.18em] text-amber-100/34">
                      open detail
                    </p>
                  ) : (
                    <p className="text-[11px] uppercase tracking-[0.18em] text-[#82ffc1]">
                      dynamic editable agent
                    </p>
                  )}
                  <p className="text-sm leading-7 text-amber-100/56">
                    {a.description || "No description provided for this registry entry."}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {a.preferred_role ? <Badge color="warning">role {a.preferred_role}</Badge> : null}
                    {a.preferred_provider ? (
                      <Badge color="muted">{a.preferred_provider}</Badge>
                    ) : null}
                    {a.preferred_model ? (
                      <Badge color="muted">{a.preferred_model}</Badge>
                    ) : null}
                    {a.strategy ? <Badge color="muted">{a.strategy}</Badge> : null}
                    {a.routing_policy ? <Badge color="muted">policy {a.routing_policy}</Badge> : null}
                  </div>
                </Card>
              </Link>
            );
          })}
        </section>
      )}

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Create Agent">
        <div className="space-y-4">
          <Input
            label="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="my-agent"
          />
          <Input
            label="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="What does this agent do?"
          />
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Preferred Provider"
              value={form.preferred_provider}
              onChange={(e) => setForm({ ...form, preferred_provider: e.target.value })}
              placeholder="ollama, mistral, bedrock..."
            />
            <Input
              label="Preferred Model"
              value={form.preferred_model}
              onChange={(e) => setForm({ ...form, preferred_model: e.target.value })}
              placeholder="llama3.2:3b, mistral-large-latest..."
            />
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <Input
              label="Preferred Role"
              value={form.preferred_role}
              onChange={(e) => setForm({ ...form, preferred_role: e.target.value })}
              placeholder="gpu, edge, general..."
            />
            <Select
              label="Strategy"
              value={form.strategy}
              onChange={(e) => setForm({ ...form, strategy: e.target.value })}
              options={strategyOptions}
            />
            <Select
              label="Routing Policy"
              value={form.routing_policy}
              onChange={(e) => setForm({ ...form, routing_policy: e.target.value })}
              options={routingPolicyOptions}
            />
          </div>
          <Textarea
            label="System Prompt"
            value={form.system_prompt}
            onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
            placeholder="You are..."
            rows={6}
          />
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Temperature"
              type="number"
              min="0"
              max="2"
              step="0.1"
              value={String(form.temperature)}
              onChange={(e) =>
                setForm({
                  ...form,
                  temperature: Number.isFinite(Number(e.target.value))
                    ? Number(e.target.value)
                    : 0.7,
                })
              }
            />
            <Input
              label="Max Tokens"
              type="number"
              min="1"
              max="128000"
              step="1"
              value={String(form.max_tokens)}
              onChange={(e) =>
                setForm({
                  ...form,
                  max_tokens: Number.isFinite(Number(e.target.value))
                    ? Number(e.target.value)
                    : 4096,
                })
              }
            />
          </div>
          <p className="text-[12px] leading-6 text-amber-100/46">
            `preferred_role` alimente maintenant le routage auto cluster. Un agent cree depuis l&apos;UI peut donc cibler directement un noeud `gpu`, `edge` ou `general`.
          </p>
          {createError ? (
            <InlineNotice title="create failed" message={createError} tone="error" />
          ) : null}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowCreate(false)}>
              cancel
            </Button>
            <Button onClick={handleCreate} loading={creating} disabled={!form.name || !form.system_prompt}>
              create
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
