import { useMemo, useState } from "react";
import { agentsApi, type Agent } from "../api/agents";
import { useApi } from "../hooks/useApi";
import { useFetch } from "../hooks/useFetch";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  InlineNotice,
  Input,
  JsonView,
  LoadingPanel,
  Textarea,
} from "../components/ui";

const orchestrationPresets = [
  {
    label: "Incident review",
    prompt:
      "Analyse un incident de stack locale, priorise les causes probables et propose un plan d'action operateur.",
  },
  {
    label: "Architecture critique",
    prompt:
      "Relis cette architecture multi-agents, identifie les zones de couplage risquee et propose une version plus robuste.",
  },
  {
    label: "Delivery split",
    prompt:
      "Decoupe une demande produit complexe en sous-taches, attribue les taches aux bons agents et liste les dependances.",
  },
];

function inferCluster(agentName: string): string {
  if (["planner", "critic", "reviewer"].includes(agentName)) return "control";
  if (agentName.includes("kicad") || agentName.includes("freecad")) return "design";
  if (agentName.includes("spice") || agentName.includes("power") || agentName.includes("emc")) {
    return "electronics";
  }
  return "runtime";
}

export default function Orchestrate() {
  const { data, loading, error, refetch } = useFetch<{ agents: Agent[] }>("/api/agents");
  const [prompt, setPrompt] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState("");

  const canRun = prompt.trim().length > 0 && selected.length > 0;
  const agents = data?.agents ?? [];

  const filteredAgents = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return agents;
    return agents.filter((agent) => {
      const haystack = `${agent.name} ${agent.description}`.toLowerCase();
      return haystack.includes(needle);
    });
  }, [agents, query]);

  const runFn = useMemo(
    () => () => agentsApi.orchestrate({ agent_names: selected, prompt }),
    [prompt, selected],
  );
  const {
    execute,
    data: result,
    loading: running,
    error: runError,
    status: runStatus,
  } = useApi(runFn);

  const selectedAgents = useMemo(
    () => agents.filter((agent) => selected.includes(agent.name)),
    [agents, selected],
  );

  const handleRun = () => {
    if (!canRun) return;
    void execute(undefined);
  };

  const toggleAgent = (name: string) => {
    setSelected((current) =>
      current.includes(name)
        ? current.filter((value) => value !== name)
        : [...current, name],
    );
  };

  if (loading && !data) {
    return (
      <LoadingPanel
        title="Loading orchestration lane"
        message="Collecting the current agent registry before arming the next cluster."
      />
    );
  }
  if (error) {
    return (
      <InlineNotice
        title="registry error"
        message={error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">orchestration lane</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                Dispatch one prompt across a controlled agent cluster
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Selectionne un groupe d'agents, envoie une consigne unique, puis lis la sequence consolidee retournee par l'API d'orchestration sans perdre le contexte du cockpit.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                  armed {selected.length}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  registry {agents.length}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  prompt {prompt.trim().length} chars
                </span>
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <Button
                  className="rounded-2xl px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  disabled={!canRun}
                  loading={running}
                  onClick={handleRun}
                >
                  run orchestration
                </Button>
                <Button
                  variant="ghost"
                  className="rounded-2xl border border-border/80 px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  onClick={() => {
                    setPrompt("");
                    setSelected([]);
                    setQuery("");
                  }}
                >
                  reset lane
                </Button>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">selected agents</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {selected.length.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Nombre d'agents armes pour la run courante.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">visible registry</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {filteredAgents.length.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Nombre d'agents visibles apres filtrage local.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">dispatch state</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {result ? "loaded" : running ? "running" : "idle"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Etat de la derniere run d'orchestration visible dans cette page.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">result steps</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {(result?.results?.length ?? 0).toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Nombre d'etapes remontees par l'orchestrateur sur la derniere run.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Dispatch controls" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/58">
              La run part uniquement si une consigne existe et si au moins un agent est arme. Le filtre sert juste a lire le registre plus vite.
            </p>
            <Input
              label="Filter registry"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="planner, kicad, spice, runtime..."
            />
            <div className="flex flex-wrap gap-2">
              {["planner", "spice", "embedded", "kicad"].map((token) => (
                <button
                  key={token}
                  type="button"
                  className="status-chip border-border/80 bg-black/30 text-muted transition hover:border-accent/35 hover:text-accent"
                  onClick={() => setQuery(token)}
                >
                  {token}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-3">
              <Button variant="secondary" onClick={() => void refetch()}>
                refresh registry
              </Button>
              <Button
                variant="ghost"
                className="border border-border/80"
                onClick={() => setSelected(filteredAgents.map((agent) => agent.name))}
              >
                arm visible
              </Button>
              <Button
                variant="ghost"
                className="border border-border/80"
                onClick={() => setSelected([])}
              >
                clear armed
              </Button>
            </div>
          </div>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Card title="Compose orchestration">
          <div className="space-y-4">
            <Textarea
              label="Prompt"
              rows={8}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Decris ici la tache globale a decomposer ou a faire traiter par le cluster d'agents selectionne."
            />
            <div className="flex flex-wrap gap-2">
              {orchestrationPresets.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => setPrompt(preset.prompt)}
                  className="rounded-2xl border border-border/80 bg-black/25 px-3 py-2 text-[11px] uppercase tracking-[0.16em] text-amber-100/72 transition hover:border-accent/35 hover:text-accent"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
        </Card>

        <Card title="Armed cluster">
          {selectedAgents.length === 0 ? (
            <EmptyState message="No agents armed for the current orchestration." />
          ) : (
            <div className="space-y-3">
              {selectedAgents.map((agent) => (
                <div
                  key={agent.name}
                  className="rounded-3xl border border-border/80 bg-black/25 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="screen-label">{inferCluster(agent.name)}</p>
                      <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                        {agent.name}
                      </p>
                    </div>
                    <Badge color="accent">armed</Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-amber-100/56">
                    {agent.description || "No description"}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </section>

      <Card title="Agent selection">
        {filteredAgents.length === 0 ? (
          <EmptyState
            message="No agents match the current filter."
            action={
              <Button variant="secondary" onClick={() => setQuery("")}>
                Clear filter
              </Button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {filteredAgents.map((agent) => {
              const active = selected.includes(agent.name);
              return (
                <button
                  key={agent.name}
                  aria-pressed={active}
                  onClick={() => toggleAgent(agent.name)}
                  className={[
                    "rounded-[1.5rem] border px-4 py-4 text-left transition-colors",
                    active
                      ? "border-accent/45 bg-accent/10 text-accent"
                      : "border-border/80 bg-black/25 text-amber-100/74 hover:border-accent/35 hover:bg-black/35",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="screen-label">{inferCluster(agent.name)}</p>
                      <p className="mt-2 text-[12px] font-semibold uppercase tracking-[0.16em]">
                        {agent.name}
                      </p>
                    </div>
                    <Badge color={active ? "accent" : "muted"}>
                      {active ? "armed" : "idle"}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-amber-100/48">
                    {agent.description || "No description"}
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </Card>

      {running ? (
        <LoadingPanel
          compact
          title="Dispatch in flight"
          message="The armed cluster is processing the current prompt through the orchestration API."
        />
      ) : null}

      {runError ? (
        <InlineNotice
          title="dispatch error"
          message={runError}
          tone="error"
        />
      ) : null}

      {result ? (
        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
          <Card title="Execution steps">
            <div className="space-y-3">
              {runStatus === "success" ? (
                <InlineNotice
                  title="dispatch complete"
                  message={`${result.results?.length ?? 0} step(s) returned by the current orchestration run.`}
                  tone="success"
                />
              ) : null}
              {result.results?.map((row) => (
                <div
                  key={`${row.agent}-${row.step}`}
                  className="rounded-[1.5rem] border border-border/80 bg-black/25 p-4"
                >
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
                    <div className="flex flex-wrap gap-2">
                      <Badge color="accent">{row.agent}</Badge>
                      <Badge color="muted">step {row.step}</Badge>
                    </div>
                    <span>
                      {row.provider} / {row.model}
                    </span>
                  </div>
                  <pre className="whitespace-pre-wrap text-sm leading-7 text-amber-100/76">
                    {row.content}
                  </pre>
                </div>
              ))}
            </div>
          </Card>

          <Card title="Raw orchestration payload">
            <JsonView data={result} />
          </Card>
        </section>
      ) : null}
    </div>
  );
}
