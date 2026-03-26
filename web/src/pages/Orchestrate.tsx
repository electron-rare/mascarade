import { useMemo, useState } from "react";
import { agentsApi, type Agent } from "../api/agents";
import { cadApi } from "../api/cad";
import { getErrorMessage } from "../api/client";
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
  Select,
  Textarea,
} from "../components/ui";

const orchestrationPresets = [
  {
    label: "Operator copilot",
    prompt:
      "Cadre cet incident operateur: resume les signaux visibles, priorise les causes probables et propose la prochaine action manuelle la plus sure.",
  },
  {
    label: "Zero intake",
    prompt:
      "Cadre cette demande de bout en bout: objectif reel, hypotheses, plan court, risques et prochaine action immediate.",
  },
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

const roleOptions = [
  { value: "", label: "Inherit agent profile" },
  { value: "general", label: "General" },
  { value: "gpu", label: "GPU" },
  { value: "edge", label: "Edge" },
  { value: "worker", label: "Worker" },
  { value: "builder", label: "Builder" },
];

const routingPolicyOverrideOptions = [
  { value: "", label: "Inherit agent policy" },
  { value: "auto", label: "Auto" },
  { value: "strong", label: "Strong" },
  { value: "cheap", label: "Cheap" },
  { value: "fast", label: "Fast" },
];

type RunRoutingOverride = {
  preferred_role: string;
  preferred_provider: string;
  preferred_model: string;
  routing_policy: string;
};

type CadActionResult = {
  kind: "freecad-create" | "openscad-render";
  run_id: string;
  payload: unknown;
};

function inferCluster(agentName: string): string {
  if (["agent-zero", "planner", "critic", "reviewer"].includes(agentName)) return "control";
  if (agentName.includes("kicad") || agentName.includes("freecad")) return "design";
  if (agentName.includes("spice") || agentName.includes("power") || agentName.includes("emc")) {
    return "electronics";
  }
  return "runtime";
}

function formatLatency(ms?: number | null): string | null {
  if (!Number.isFinite(ms) || ms === undefined || ms === null || ms < 0) return null;
  return `${Math.round(ms)} ms`;
}

export default function Orchestrate() {
  const { data, loading, error, refetch } = useFetch<{ agents: Agent[] }>("/api/agents");
  const [prompt, setPrompt] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [routingForm, setRoutingForm] = useState<Record<string, RunRoutingOverride>>({});
  const [mcpServerFilter, setMcpServerFilter] = useState("");
  const [mcpToolFilter, setMcpToolFilter] = useState("");
  const [mcpStatusFilter, setMcpStatusFilter] = useState("");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [cadBusy, setCadBusy] = useState<"freecad" | "openscad" | null>(null);
  const [cadError, setCadError] = useState<string | null>(null);
  const [cadResult, setCadResult] = useState<CadActionResult | null>(null);
  const [freecadDocumentPath, setFreecadDocumentPath] = useState(
    ".cad-home/freecad-orchestrate/trace-run.FCStd",
  );
  const [freecadDocumentName, setFreecadDocumentName] = useState("TraceDoc");
  const [openscadOutputPath, setOpenscadOutputPath] = useState(
    ".cad-home/openscad-orchestrate/trace-run.stl",
  );
  const [openscadSource, setOpenscadSource] = useState("cube([10, 8, 6]);");

  const canRun = prompt.trim().length > 0 && selected.length > 0;
  const agents = data?.agents ?? [];
  const hasAgentZero = agents.some((agent) => agent.name === "agent-zero");

  const routingOverrides = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(routingForm)
          .filter(([agentName, override]) => {
            if (!selected.includes(agentName)) return false;
            return Boolean(
              override.preferred_role.trim() ||
                override.preferred_provider.trim() ||
                override.preferred_model.trim() ||
                override.routing_policy.trim(),
            );
          })
          .map(([agentName, override]) => [
            agentName,
            {
              ...(override.preferred_role.trim()
                ? { preferred_role: override.preferred_role.trim() }
                : {}),
              ...(override.preferred_provider.trim()
                ? { preferred_provider: override.preferred_provider.trim() }
                : {}),
              ...(override.preferred_model.trim()
                ? { preferred_model: override.preferred_model.trim() }
                : {}),
              ...(override.routing_policy.trim()
                ? { routing_policy: override.routing_policy.trim() }
                : {}),
            },
          ]),
      ),
    [routingForm, selected],
  );

  const filteredAgents = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return agents;
    return agents.filter((agent) => {
      const haystack = `${agent.name} ${agent.description}`.toLowerCase();
      return haystack.includes(needle);
    });
  }, [agents, query]);

  const runFn = useMemo(
    () => () =>
      agentsApi.orchestrate({
        agent_names: selected,
        prompt,
        routing_overrides: routingOverrides,
      }),
    [prompt, routingOverrides, selected],
  );
  const {
    execute,
    data: result,
    loading: running,
    error: runError,
    status: runStatus,
  } = useApi(runFn);
  const runTrace = useFetch<{
    run_id: string;
    count: number;
      events: {
        id: string;
        ts: string;
        event_type: string;
        message: string;
        agent_name?: string | null;
        from_agent?: string | null;
        to_agent?: string | null;
        prompt_excerpt?: string | null;
        content_excerpt?: string | null;
        routing_role?: string | null;
        routing_provider?: string | null;
        routing_model?: string | null;
        routing_policy?: string | null;
        routing_selected_by?: string | null;
        routing_transport?: string | null;
        routing_latency_ms?: number | null;
        mcp_server?: string | null;
        mcp_tool?: string | null;
        mcp_status?: string | null;
        mcp_transport?: string | null;
        mcp_latency_ms?: number | null;
        mcp_protocol_version?: string | null;
        error?: string | null;
      }[];
  }>(
    activeRunId
      ? `/api/ops/agent-traces/${encodeURIComponent(activeRunId)}?limit=120`
      : null,
    { pollIntervalMs: activeRunId ? 1400 : undefined, timeoutMs: 20000 },
  );

  const selectedAgents = useMemo(
    () => agents.filter((agent) => selected.includes(agent.name)),
    [agents, selected],
  );
  const traceEvents = runTrace.data?.events ?? [];
  const mcpEvents = useMemo(
    () => traceEvents.filter((event) => Boolean(event.mcp_server)),
    [traceEvents],
  );
  const mcpServers = useMemo(
    () =>
      Array.from(new Set(mcpEvents.map((event) => event.mcp_server).filter(Boolean))) as string[],
    [mcpEvents],
  );
  const mcpTools = useMemo(
    () =>
      Array.from(new Set(mcpEvents.map((event) => event.mcp_tool).filter(Boolean))) as string[],
    [mcpEvents],
  );
  const mcpStatuses = useMemo(
    () =>
      Array.from(new Set(mcpEvents.map((event) => event.mcp_status).filter(Boolean))) as string[],
    [mcpEvents],
  );
  const filteredTraceEvents = useMemo(
    () =>
      traceEvents.filter((event) => {
        if (mcpServerFilter && event.mcp_server !== mcpServerFilter) return false;
        if (mcpToolFilter && event.mcp_tool !== mcpToolFilter) return false;
        if (mcpStatusFilter && event.mcp_status !== mcpStatusFilter) return false;
        return true;
      }),
    [mcpServerFilter, mcpStatusFilter, mcpToolFilter, traceEvents],
  );

  const handleRun = async () => {
    if (!canRun) return;
    const payload = await execute(undefined);
    if (payload?.run_id) {
      setActiveRunId(payload.run_id);
      setCadResult(null);
      setCadError(null);
    }
  };

  const handleCadAction = async (kind: "freecad" | "openscad") => {
    const runId =
      globalThis.crypto?.randomUUID?.() ?? `cad-run-${Date.now().toString(36)}`;
    setCadBusy(kind);
    setCadError(null);
    try {
      const payload =
        kind === "freecad"
          ? await cadApi.freecadCreateDocument({
              output_path: freecadDocumentPath,
              name: freecadDocumentName,
              run_id: runId,
            })
          : await cadApi.openscadRenderModel({
              source: openscadSource,
              output_path: openscadOutputPath,
              run_id: runId,
            });
      setCadResult({
        kind: kind === "freecad" ? "freecad-create" : "openscad-render",
        run_id: payload.run_id,
        payload,
      });
      setActiveRunId(payload.run_id);
    } catch (error) {
      setCadError(getErrorMessage(error));
    } finally {
      setCadBusy(null);
    }
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
              <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">orchestration lane</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent font-bold text-accent md:text-5xl">
                Dispatch one prompt across a controlled agent cluster
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-[#1d1d1f]/60 md:text-[15px]">
                Selectionne un groupe d'agents, envoie une consigne unique, puis lis la sequence consolidee retournee par l'API d'orchestration sans perdre le contexte du cockpit.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="status-chip border-accent/15 bg-accent/10 text-accent">
                  armed {selected.length}
                </span>
                <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">
                  registry {agents.length}
                </span>
                <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">
                  prompt {prompt.trim().length} chars
                </span>
                <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">
                  role overrides {Object.keys(routingOverrides).length}
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
                  className="rounded-2xl border border-[rgba(0,0,0,0.08)] px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  onClick={() => {
                    setPrompt("");
                    setSelected([]);
                    setQuery("");
                    setRoutingForm({});
                    setCadError(null);
                    setCadResult(null);
                    setActiveRunId(null);
                  }}
                >
                  reset lane
                </Button>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">selected agents</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {selected.length.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                  Nombre d'agents armes pour la run courante.
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">visible registry</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {filteredAgents.length.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                  Nombre d'agents visibles apres filtrage local.
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">dispatch state</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {result ? "loaded" : running ? "running" : "idle"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                  Etat de la derniere run d'orchestration visible dans cette page.
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">result steps</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {(result?.results?.length ?? 0).toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                  Nombre d'etapes remontees par l'orchestrateur sur la derniere run.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Dispatch controls" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-[#86868b]">
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
                  className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted transition hover:border-accent/15 hover:text-accent"
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
              {hasAgentZero ? (
                <Button
                  variant="ghost"
                  className="border border-accent/15 text-accent"
                  onClick={() =>
                    setSelected((current) =>
                      current.includes("agent-zero") ? current : ["agent-zero", ...current],
                    )
                  }
                >
                  arm agent-zero
                </Button>
              ) : null}
              <Button
                variant="ghost"
                className="border border-[rgba(0,0,0,0.08)]"
                onClick={() => setSelected(filteredAgents.map((agent) => agent.name))}
              >
                arm visible
              </Button>
                <Button
                  variant="ghost"
                  className="border border-[rgba(0,0,0,0.08)]"
                  onClick={() => {
                    setSelected([]);
                    setRoutingForm({});
                  }}
                >
                  clear armed
                </Button>
            </div>
          </div>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Card title="CAD MCP actions">
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">freecad</p>
                  <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                    create traced document
                  </p>
                </div>
                <Badge color="accent">mcp</Badge>
              </div>
              <p className="mt-3 text-sm leading-6 text-[#1d1d1f]/56">
                Cree un document headless minimal via la façade MCP core, puis suit les événements corrélés dans la timeline avec le même run ID.
              </p>
              <div className="mt-4 space-y-3">
                <Input
                  label="Document path"
                  value={freecadDocumentPath}
                  onChange={(e) => setFreecadDocumentPath(e.target.value)}
                  placeholder=".cad-home/freecad-orchestrate/trace-run.FCStd"
                />
                <Input
                  label="Document name"
                  value={freecadDocumentName}
                  onChange={(e) => setFreecadDocumentName(e.target.value)}
                  placeholder="TraceDoc"
                />
                <Button
                  className="rounded-2xl px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  loading={cadBusy === "freecad"}
                  onClick={() => void handleCadAction("freecad")}
                >
                  run freecad mcp
                </Button>
              </div>
            </div>
            <div className="rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">openscad</p>
                  <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                    render traced model
                  </p>
                </div>
                <Badge color="accent">mcp</Badge>
              </div>
              <p className="mt-3 text-sm leading-6 text-[#1d1d1f]/56">
                Rend un modèle minimal via OpenSCAD headless et remonte le run corrélé dans la même timeline que les autres appels MCP.
              </p>
              <div className="mt-4 space-y-3">
                <Input
                  label="Output path"
                  value={openscadOutputPath}
                  onChange={(e) => setOpenscadOutputPath(e.target.value)}
                  placeholder=".cad-home/openscad-orchestrate/trace-run.stl"
                />
                <Textarea
                  label="Source"
                  rows={5}
                  value={openscadSource}
                  onChange={(e) => setOpenscadSource(e.target.value)}
                  placeholder="cube([10, 8, 6]);"
                />
                <Button
                  className="rounded-2xl px-4 py-2 text-xs uppercase tracking-[0.18em]"
                  loading={cadBusy === "openscad"}
                  onClick={() => void handleCadAction("openscad")}
                >
                  run openscad mcp
                </Button>
              </div>
            </div>
          </div>
          {cadError ? (
            <InlineNotice
              title="cad action error"
              message={cadError}
              tone="error"
              className="mt-4"
            />
          ) : null}
          {cadResult ? (
            <div className="mt-4 space-y-3">
              <InlineNotice
                title="cad action complete"
                message={`${cadResult.kind} finished with run_id=${cadResult.run_id}`}
                tone="success"
              />
              <JsonView data={cadResult.payload} />
            </div>
          ) : null}
        </Card>

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
                  onClick={() => {
                    setPrompt(preset.prompt);
                    if (preset.label === "Zero intake" && hasAgentZero) {
                      setSelected((current) =>
                        current.includes("agent-zero") ? current : ["agent-zero", ...current],
                      );
                    }
                  }}
                  className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-3 py-2 text-[11px] uppercase tracking-[0.16em] text-[#6e6e73] transition hover:border-accent/15 hover:text-accent"
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
                  className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">{inferCluster(agent.name)}</p>
                      <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                        {agent.name}
                      </p>
                    </div>
                    <Badge color="accent">armed</Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-[#1d1d1f]/56">
                    {agent.description || "No description"}
                  </p>
                  <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,1fr)_200px] md:items-end">
                    <div className="space-y-2">
                      <div className="flex flex-wrap gap-2">
                        {agent.preferred_role ? (
                          <Badge color="warning">profile {agent.preferred_role}</Badge>
                        ) : (
                          <Badge color="muted">profile inherit</Badge>
                        )}
                        {agent.routing_policy ? (
                          <Badge color="muted">policy {agent.routing_policy}</Badge>
                        ) : null}
                        {routingForm[agent.name]?.preferred_role?.trim() ? (
                          <Badge color="accent">
                            run role {routingForm[agent.name].preferred_role}
                          </Badge>
                        ) : null}
                        {routingForm[agent.name]?.preferred_provider?.trim() ? (
                          <Badge color="accent">
                            run provider {routingForm[agent.name].preferred_provider}
                          </Badge>
                        ) : null}
                        {routingForm[agent.name]?.preferred_model?.trim() ? (
                          <Badge color="accent">
                            run model {routingForm[agent.name].preferred_model}
                          </Badge>
                        ) : null}
                        {routingForm[agent.name]?.routing_policy?.trim() ? (
                          <Badge color="accent">
                            run policy {routingForm[agent.name].routing_policy}
                          </Badge>
                        ) : null}
                      </div>
                      <p className="text-[12px] leading-5 text-[#1d1d1f]/46">
                        Override role, provider, model or routing policy for this run only. Leave a field empty to inherit the stored agent profile.
                      </p>
                    </div>
                    <div className="space-y-4">
                      <Select
                        label="Role override"
                        value={routingForm[agent.name]?.preferred_role ?? ""}
                        onChange={(e) =>
                          setRoutingForm((current) => ({
                            ...current,
                            [agent.name]: {
                              preferred_role: e.target.value,
                              preferred_provider:
                                current[agent.name]?.preferred_provider ?? "",
                              preferred_model:
                                current[agent.name]?.preferred_model ?? "",
                              routing_policy:
                                current[agent.name]?.routing_policy ?? "",
                            },
                          }))
                        }
                        options={roleOptions}
                      />
                      <Input
                        label="Provider override"
                        value={routingForm[agent.name]?.preferred_provider ?? ""}
                        onChange={(e) =>
                          setRoutingForm((current) => ({
                            ...current,
                            [agent.name]: {
                              preferred_role: current[agent.name]?.preferred_role ?? "",
                              preferred_provider: e.target.value,
                              preferred_model:
                                current[agent.name]?.preferred_model ?? "",
                              routing_policy:
                                current[agent.name]?.routing_policy ?? "",
                            },
                          }))
                        }
                        placeholder="ollama, mistral, bedrock..."
                      />
                      <Input
                        label="Model override"
                        value={routingForm[agent.name]?.preferred_model ?? ""}
                        onChange={(e) =>
                          setRoutingForm((current) => ({
                            ...current,
                            [agent.name]: {
                              preferred_role: current[agent.name]?.preferred_role ?? "",
                              preferred_provider:
                                current[agent.name]?.preferred_provider ?? "",
                              preferred_model: e.target.value,
                              routing_policy:
                                current[agent.name]?.routing_policy ?? "",
                            },
                          }))
                        }
                        placeholder="llama3.2:3b, mistral-large-latest..."
                      />
                      <Select
                        label="Routing policy override"
                        value={routingForm[agent.name]?.routing_policy ?? ""}
                        onChange={(e) =>
                          setRoutingForm((current) => ({
                            ...current,
                            [agent.name]: {
                              preferred_role: current[agent.name]?.preferred_role ?? "",
                              preferred_provider:
                                current[agent.name]?.preferred_provider ?? "",
                              preferred_model:
                                current[agent.name]?.preferred_model ?? "",
                              routing_policy: e.target.value,
                            },
                          }))
                        }
                        options={routingPolicyOverrideOptions}
                      />
                    </div>
                  </div>
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
                      : "border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-[#1d1d1f]/74 hover:border-accent/15 hover:bg-[#f5f5f7]",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">{inferCluster(agent.name)}</p>
                      <p className="mt-2 text-[12px] font-semibold uppercase tracking-[0.16em]">
                        {agent.name}
                      </p>
                    </div>
                    <Badge color={active ? "accent" : "muted"}>
                      {active ? "armed" : "idle"}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-[#1d1d1f]/48">
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

      {result || cadResult || activeRunId ? (
        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
          <Card title={result ? "Execution steps" : "CAD MCP action"}>
            {result ? (
              <div className="space-y-3">
                {runStatus === "success" ? (
                  <InlineNotice
                    title="dispatch complete"
                    message={`${result.results?.length ?? 0} step(s) returned by the current orchestration run. run_id=${result.run_id}`}
                    tone="success"
                  />
                ) : null}
                {result.results?.map((row) => (
                  <div
                    key={`${row.agent}-${row.step}`}
                    className="rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4"
                  >
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
                      <div className="flex flex-wrap gap-2">
                        <Badge color="accent">{row.agent}</Badge>
                        <Badge color="muted">step {row.step}</Badge>
                        <Badge color={row.remote ? "warning" : "muted"}>
                          {row.remote ? "remote" : "local"}
                        </Badge>
                        {row.selected_by ? (
                          <Badge color="muted">route {row.selected_by}</Badge>
                        ) : null}
                        {row.transport ? (
                          <Badge color="muted">transport {row.transport}</Badge>
                        ) : null}
                        {formatLatency(row.latency_ms) ? (
                          <Badge color="warning">{formatLatency(row.latency_ms)}</Badge>
                        ) : null}
                        {row.role ? <Badge color="muted">role {row.role}</Badge> : null}
                      </div>
                      <span>
                        {row.provider} / {row.model}
                      </span>
                    </div>
                    {row.node_id || row.peer_id ? (
                      <p className="mb-3 text-[12px] leading-5 text-[#1d1d1f]/46">
                        route: node {row.node_id || "local"} {row.peer_id ? `via ${row.peer_id}` : ""}
                      </p>
                    ) : null}
                    <pre className="whitespace-pre-wrap text-sm leading-7 text-[#1d1d1f]/76">
                      {row.content}
                    </pre>
                    {row.error ? (
                      <p className="mt-3 text-sm leading-6 text-error">
                        error: {row.error}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : cadResult ? (
              <div className="space-y-3">
                <InlineNotice
                  title="cad action complete"
                  message={`${cadResult.kind} finished with run_id=${cadResult.run_id}`}
                  tone="success"
                />
                <JsonView data={cadResult.payload} />
              </div>
            ) : (
              <EmptyState message="No orchestration payload or CAD action selected yet." />
            )}
          </Card>

          <div className="space-y-4">
            <Card title="Live run trace">
              {runTrace.loading && !runTrace.data ? (
                <LoadingPanel
                  compact
                  title="Loading run trace"
                  message="Following the structured trace emitted by the core for the current run."
                />
              ) : runTrace.error && !runTrace.data ? (
                <InlineNotice title="trace error" message={runTrace.error} tone="error" />
              ) : !runTrace.data || runTrace.data.events.length === 0 ? (
                <EmptyState message="No trace event recorded yet for this run." />
              ) : (
                <div className="space-y-4">
                  <div className="rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge color="accent">run {activeRunId}</Badge>
                      <Badge color="muted">events {traceEvents.length}</Badge>
                      <Badge color="accent">mcp {mcpEvents.length}</Badge>
                      <Badge color="muted">
                        visible {filteredTraceEvents.length}
                      </Badge>
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                      <Select
                        label="MCP server"
                        value={mcpServerFilter}
                        onChange={(e) => setMcpServerFilter(e.target.value)}
                        options={[
                          { value: "", label: "All servers" },
                          ...mcpServers.map((value) => ({ value, label: value })),
                        ]}
                      />
                      <Select
                        label="MCP tool"
                        value={mcpToolFilter}
                        onChange={(e) => setMcpToolFilter(e.target.value)}
                        options={[
                          { value: "", label: "All tools" },
                          ...mcpTools.map((value) => ({ value, label: value })),
                        ]}
                      />
                      <Select
                        label="MCP status"
                        value={mcpStatusFilter}
                        onChange={(e) => setMcpStatusFilter(e.target.value)}
                        options={[
                          { value: "", label: "All statuses" },
                          ...mcpStatuses.map((value) => ({ value, label: value })),
                        ]}
                      />
                    </div>
                  </div>
                  <div className="max-h-[520px] space-y-3 overflow-y-auto pr-1">
                    {filteredTraceEvents.map((event) => (
                    <div
                      key={event.id}
                      className="rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4"
                    >
                      <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.18em]">
                        <span className="text-muted">{event.ts.slice(11, 19)}</span>
                        <span className="text-accent">{event.event_type}</span>
                        {event.agent_name ? (
                          <Badge color="accent">{event.agent_name}</Badge>
                        ) : null}
                        {event.from_agent && event.to_agent ? (
                          <span className="status-chip border-[#214e31] bg-[#0c170f]/80 text-[#82ffc1]">
                            {event.from_agent} → {event.to_agent}
                          </span>
                        ) : null}
                        {event.mcp_server ? (
                          <Badge color="accent">{event.mcp_server}</Badge>
                        ) : null}
                        {event.mcp_tool ? (
                          <Badge color="muted">{event.mcp_tool}</Badge>
                        ) : null}
                        {event.mcp_status ? (
                          <Badge color={event.mcp_status === "error" || event.mcp_status === "timeout" ? "error" : "warning"}>
                            {event.mcp_status}
                          </Badge>
                        ) : null}
                      </div>
                      <p className="mt-3 text-sm leading-6 text-[#1d1d1f]/74">
                        {event.message}
                      </p>
                      {event.mcp_server || event.mcp_tool || event.mcp_transport || event.mcp_protocol_version ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {event.mcp_transport ? (
                            <Badge color="muted">transport {event.mcp_transport}</Badge>
                          ) : null}
                          {event.mcp_protocol_version ? (
                            <Badge color="muted">protocol {event.mcp_protocol_version}</Badge>
                          ) : null}
                          {event.mcp_latency_ms !== undefined && event.mcp_latency_ms !== null ? (
                            <Badge color="warning">
                              {event.mcp_latency_ms.toFixed(1)} ms
                            </Badge>
                          ) : null}
                        </div>
                      ) : null}
                      {event.routing_selected_by ||
                      event.routing_transport ||
                      event.routing_latency_ms !== undefined && event.routing_latency_ms !== null ||
                      event.routing_role ||
                      event.routing_provider ||
                      event.routing_model ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {event.routing_selected_by ? (
                            <Badge color="muted">route {event.routing_selected_by}</Badge>
                          ) : null}
                          {event.routing_transport ? (
                            <Badge color="muted">transport {event.routing_transport}</Badge>
                          ) : null}
                          {formatLatency(event.routing_latency_ms) ? (
                            <Badge color="warning">{formatLatency(event.routing_latency_ms)}</Badge>
                          ) : null}
                          {event.routing_role ? (
                            <Badge color="warning">role {event.routing_role}</Badge>
                          ) : null}
                          {event.routing_provider ? (
                            <Badge color="muted">provider {event.routing_provider}</Badge>
                          ) : null}
                          {event.routing_model ? (
                            <Badge color="muted">model {event.routing_model}</Badge>
                          ) : null}
                        </div>
                      ) : null}
                      {event.prompt_excerpt ? (
                        <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                          input: {event.prompt_excerpt}
                        </p>
                      ) : null}
                      {event.content_excerpt ? (
                        <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                          output: {event.content_excerpt}
                        </p>
                      ) : null}
                      {event.error ? (
                        <p className="mt-2 text-[12px] leading-5 text-error">
                          error: {event.error}
                        </p>
                      ) : null}
                    </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>

            <Card title={result ? "Raw orchestration payload" : "Raw CAD payload"}>
              <JsonView data={result ?? cadResult?.payload ?? { run_id: activeRunId }} />
            </Card>
          </div>
        </section>
      ) : null}
    </div>
  );
}
