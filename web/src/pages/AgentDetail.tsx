import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  agentsApi,
  type Agent,
  type AgentGate,
  type AgentMetrics,
  type PromptVersionInfo,
} from "../api/agents";
import { useApi } from "../hooks/useApi";
import { useFetch } from "../hooks/useFetch";
import {
  Badge,
  Button,
  Card,
  InlineNotice,
  Input,
  LoadingPanel,
  Modal,
  Select,
  Textarea,
} from "../components/ui";
import PromptEditor from "../components/PromptEditor";

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

type AgentProfileForm = {
  description: string;
  system_prompt: string;
  preferred_provider: string;
  preferred_model: string;
  preferred_role: string;
  strategy: string;
  routing_policy: string;
  temperature: number;
  max_tokens: number;
  tools: string;
  skills: string;
  category: string;
  cluster: string;
  capabilities: string;
  evidence_refs: string;
  retry_config: string;
  gates: string;
  version_note: string;
};

function normalizeOptional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function csvFromList(values?: string[] | null): string {
  return (values || []).join(", ");
}

function parseCsv(value: string): string[] {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function jsonFromValue(value: unknown): string {
  return value ? JSON.stringify(value, null, 2) : "";
}

function parseJsonObject(value: string, fieldLabel: string): Record<string, unknown> | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = JSON.parse(trimmed) as unknown;
  if (parsed === null) return null;
  if (typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${fieldLabel} must be a JSON object`);
  }
  return parsed as Record<string, unknown>;
}

function parseJsonGates(value: string): AgentGate[] {
  const trimmed = value.trim();
  if (!trimmed) return [];
  const parsed = JSON.parse(trimmed) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error("Gates must be a JSON array");
  }
  return parsed as AgentGate[];
}

function formatStamp(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function healthStatusText(errorRate: number): string {
  if (errorRate === 0) return "healthy";
  if (errorRate < 5) return "nominal";
  if (errorRate < 20) return "watch";
  return "degraded";
}

function healthStatusOk(errorRate: number): boolean {
  return errorRate < 5;
}

export default function AgentDetail() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [formValidationError, setFormValidationError] = useState<string | null>(null);
  const isAgentZero = name === "agent-zero";

  const detail = useFetch<Agent>(name ? `/api/agents/${encodeURIComponent(name)}` : null);
  const metrics = useFetch<AgentMetrics>(
    name ? `/api/agents/${encodeURIComponent(name)}/metrics` : null,
    { pollIntervalMs: 5000 },
  );
  const [form, setForm] = useState<AgentProfileForm>({
    description: "",
    system_prompt: "",
    preferred_provider: "",
    preferred_model: "",
    preferred_role: "",
    strategy: "routellm",
    routing_policy: "auto",
    temperature: 0.7,
    max_tokens: 4096,
    tools: "",
    skills: "",
    category: "",
    cluster: "",
    capabilities: "",
    evidence_refs: "",
    retry_config: "",
    gates: "",
    version_note: "",
  });

  useEffect(() => {
    if (!detail.data) return;
    setForm({
      description: detail.data.description || "",
      system_prompt: detail.data.system_prompt || "",
      preferred_provider: detail.data.preferred_provider || "",
      preferred_model: detail.data.preferred_model || "",
      preferred_role: detail.data.preferred_role || "",
      strategy: detail.data.strategy || "routellm",
      routing_policy: detail.data.routing_policy || "auto",
      temperature: detail.data.temperature ?? 0.7,
      max_tokens: detail.data.max_tokens ?? 4096,
      tools: csvFromList(detail.data.tools),
      skills: csvFromList(detail.data.skills),
      category: detail.data.category || "",
      cluster: detail.data.cluster || "",
      capabilities: csvFromList(detail.data.capabilities),
      evidence_refs: csvFromList(detail.data.evidence_refs),
      retry_config: jsonFromValue(detail.data.retry_config),
      gates: jsonFromValue(detail.data.gates),
      version_note: "",
    });
  }, [detail.data]);

  const runFn = useCallback(
    () => agentsApi.run(name!, [{ role: "user", content: input }]),
    [name, input],
  );

  const updateFn = useCallback(
    (payload: Parameters<typeof agentsApi.update>[1]) => agentsApi.update(name!, payload),
    [name],
  );

  const {
    execute,
    data: result,
    loading,
    error,
    status,
  } = useApi(runFn);

  const {
    execute: saveProfile,
    loading: saving,
    error: saveError,
    status: saveStatus,
  } = useApi(updateFn);

  const deleteFn = useMemo(() => () => agentsApi.delete(name!), [name]);

  const {
    execute: deleteAgent,
    loading: deleting,
    error: deleteError,
  } = useApi(deleteFn);

  const rollbackApi = useApi(
    async (version: number) => agentsApi.rollbackPrompt(name!, version),
  );

  const handleRun = () => {
    if (!input.trim()) return;
    void execute(undefined);
  };

  const handleSave = async () => {
    if (!name || !form.system_prompt.trim() || detail.data?.builtin) return;
    setFormValidationError(null);
    try {
      const retry_config = parseJsonObject(form.retry_config, "Retry config");
      const gates = parseJsonGates(form.gates);
      const updated = await saveProfile({
        description: form.description,
        system_prompt: form.system_prompt,
        preferred_provider: normalizeOptional(form.preferred_provider),
        preferred_model: normalizeOptional(form.preferred_model),
        preferred_role: normalizeOptional(form.preferred_role),
        strategy: form.strategy,
        routing_policy: form.routing_policy,
        temperature: form.temperature,
        max_tokens: form.max_tokens,
        tools: parseCsv(form.tools),
        skills: parseCsv(form.skills),
        category: normalizeOptional(form.category),
        cluster: normalizeOptional(form.cluster),
        capabilities: parseCsv(form.capabilities),
        evidence_refs: parseCsv(form.evidence_refs),
        retry_config,
        gates,
        version_note: normalizeOptional(form.version_note),
      });
      if (updated) {
        setForm((current) => ({ ...current, version_note: "" }));
        void detail.refetch();
      }
    } catch (error) {
      setFormValidationError(error instanceof Error ? error.message : "Invalid advanced metadata");
      return;
    }
  };

  const handleRollback = async (version: PromptVersionInfo["version_number"]) => {
    if (!name || detail.data?.builtin) return;
    const result = await rollbackApi.execute(version);
    if (result) {
      void detail.refetch();
    }
  };

  const handleDelete = async () => {
    if (!name || detail.data?.builtin) return;
    const result = await deleteAgent(undefined);
    if (result) {
      navigate("/agents");
    }
  };

  if (detail.loading && !detail.data) {
    return (
      <LoadingPanel
        title="Loading agent surface"
        message="Collecting the selected agent profile before opening the lane."
      />
    );
  }

  if (detail.error && !detail.data) {
    return (
      <InlineNotice
        title="agent load error"
        message={detail.error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">agent focus</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent font-bold text-accent md:text-5xl">
                {name}
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-[#1d1d1f]/60 md:text-[15px]">
                Surface de test et de configuration pour l&apos;agent selectionne. Le profil ci-dessous pilote maintenant le routage auto cluster, pas seulement le prompt de systeme.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                {detail.data?.builtin ? <Badge color="muted">built-in</Badge> : null}
                {detail.data?.preferred_role ? (
                  <Badge color="warning">role {detail.data.preferred_role}</Badge>
                ) : null}
                {detail.data?.preferred_provider ? (
                  <Badge color="muted">{detail.data.preferred_provider}</Badge>
                ) : null}
                {detail.data?.preferred_model ? (
                  <Badge color="muted">{detail.data.preferred_model}</Badge>
                ) : null}
                {detail.data?.strategy ? (
                  <Badge color="muted">{detail.data.strategy}</Badge>
                ) : null}
                {detail.data?.routing_policy ? (
                  <Badge color="muted">policy {detail.data.routing_policy}</Badge>
                ) : null}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge color="accent">{name}</Badge>
              {isAgentZero ? <Badge color="accent">lead intake</Badge> : null}
              <Badge color="muted">{result ? "responded" : "idle"}</Badge>
            </div>
          </div>
        </Card>

        <Card title="Agent lane">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-[#86868b]">
              Lance un test direct, puis ajuste le profil de routage si l&apos;agent doit preferer un noeud `gpu`, `edge` ou un provider/modele donne.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button onClick={handleRun} loading={loading} disabled={!input.trim()}>
                run agent
              </Button>
              <Link
                to="/orchestrate"
                className="rounded-2xl border border-[rgba(0,0,0,0.08)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#6e6e73] transition hover:border-accent/15 hover:text-accent"
              >
                open orchestrate
              </Link>
            </div>
          </div>
        </Card>
      </section>

      {isAgentZero ? (
        <InlineNotice
          title="agent-zero posture"
          message="Utilise cet agent pour cadrer une demande floue ou un incident operateur, identifier l'objectif reel, proposer un plan court et prioriser la prochaine action manuelle avant de basculer vers des agents plus specialises."
          tone="success"
        />
      ) : null}

      {detail.data?.builtin ? (
        <InlineNotice
          title="read-only builtin"
          message="This agent is built into the registry. Its routing profile is visible here, but only dynamic agents created from the UI can be edited persistently."
          tone="info"
        />
      ) : null}

      {saveStatus === "success" ? (
        <InlineNotice
          title="profile updated"
          message={`The routing profile for ${name} was saved to the registry.`}
          tone="success"
        />
      ) : null}

      {metrics.data && Object.keys(metrics.data).length > 0 ? (
        <Card title="Agent metrics" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(6,7,7,0.98))]">
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">performance track</p>
                <p className="mt-3 text-sm leading-6 text-[#1d1d1f]/54">
                  Metriques de sante et d&apos;activite pour {name}. Les compteurs remontent depuis le core tracker du registry.
                </p>
              </div>
              <span
                className={[
                  "status-chip",
                  healthStatusOk(metrics.data.error_rate)
                    ? "border-[#e8f5e9] bg-[#f5f5f7]/80 text-[#30d158]"
                    : "border-[#fce4ec] bg-[#f5f5f7]/80 text-error",
                ].join(" ")}
              >
                {healthStatusText(metrics.data.error_rate)}
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">requests</p>
                <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                  {metrics.data.total_requests.toString().padStart(2, "0")}
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">error rate</p>
                <p
                  className={[
                    "mt-3 text-xl font-semibold uppercase tracking-[0.14em]",
                    healthStatusOk(metrics.data.error_rate) ? "text-[#30d158]" : "text-error",
                  ].join(" ")}
                >
                  {metrics.data.error_rate.toFixed(1)}%
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">latency</p>
                <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                  {metrics.data.avg_response_time > 0
                    ? `${Math.round(metrics.data.avg_response_time)} ms`
                    : "-"}
                </p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">tokens</p>
                <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                  {metrics.data.total_tokens.toLocaleString()}
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">cost</p>
                <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                  ${metrics.data.total_cost.toFixed(4)}
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">last used</p>
                <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                  {formatStamp(metrics.data.last_used)}
                </p>
              </div>
            </div>
          </div>
        </Card>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card title="Routing profile">
          <div className="space-y-4">
            <Textarea
              label="Description"
              rows={4}
              value={form.description}
              disabled={detail.data?.builtin}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <PromptEditor
              label="System Prompt"
              value={form.system_prompt}
              disabled={detail.data?.builtin}
              onChange={(value) => setForm({ ...form, system_prompt: value })}
              placeholder="Enter the system prompt for this agent..."
            />
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Preferred Provider"
                value={form.preferred_provider}
                disabled={detail.data?.builtin}
                onChange={(e) => setForm({ ...form, preferred_provider: e.target.value })}
                placeholder="ollama, mistral, bedrock..."
              />
              <Input
                label="Preferred Model"
                value={form.preferred_model}
                disabled={detail.data?.builtin}
                onChange={(e) => setForm({ ...form, preferred_model: e.target.value })}
                placeholder="llama3.2:3b, mistral-large-latest..."
              />
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <Input
                label="Preferred Role"
                value={form.preferred_role}
                disabled={detail.data?.builtin}
                onChange={(e) => setForm({ ...form, preferred_role: e.target.value })}
                placeholder="gpu, edge, general..."
              />
              <Select
                label="Strategy"
                value={form.strategy}
                disabled={detail.data?.builtin}
                onChange={(e) => setForm({ ...form, strategy: e.target.value })}
                options={strategyOptions}
              />
              <Select
                label="Routing Policy"
                value={form.routing_policy}
                disabled={detail.data?.builtin}
                onChange={(e) => setForm({ ...form, routing_policy: e.target.value })}
                options={routingPolicyOptions}
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Temperature"
                type="number"
                min="0"
                max="2"
                step="0.1"
                value={String(form.temperature)}
                disabled={detail.data?.builtin}
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
                disabled={detail.data?.builtin}
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
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Category"
                value={form.category}
                disabled={detail.data?.builtin}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                placeholder="code, ops, design..."
              />
              <Input
                label="Cluster"
                value={form.cluster}
                disabled={detail.data?.builtin}
                onChange={(e) => setForm({ ...form, cluster: e.target.value })}
                placeholder="runtime, design, control..."
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Textarea
                label="Tools (CSV)"
                rows={3}
                value={form.tools}
                disabled={detail.data?.builtin}
                onChange={(e) => setForm({ ...form, tools: e.target.value })}
                placeholder="python, kicad-mcp, filesystem"
              />
              <Textarea
                label="Skills (CSV)"
                rows={3}
                value={form.skills}
                disabled={detail.data?.builtin}
                onChange={(e) => setForm({ ...form, skills: e.target.value })}
                placeholder="json-output, concise-mode"
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Textarea
                label="Capabilities (CSV)"
                rows={3}
                value={form.capabilities}
                disabled={detail.data?.builtin}
                onChange={(e) => setForm({ ...form, capabilities: e.target.value })}
                placeholder="code, review, pcb"
              />
              <Textarea
                label="Evidence Refs (CSV)"
                rows={3}
                value={form.evidence_refs}
                disabled={detail.data?.builtin}
                onChange={(e) => setForm({ ...form, evidence_refs: e.target.value })}
                placeholder="kb://incident-42, doc://runbook"
              />
            </div>
            <Textarea
              label="Retry Config (JSON object)"
              rows={5}
              value={form.retry_config}
              disabled={detail.data?.builtin}
              onChange={(e) => setForm({ ...form, retry_config: e.target.value })}
              placeholder={'{\n  "max_attempts": 2,\n  "backoff_seconds": 1\n}'}
            />
            <Textarea
              label="Gates (JSON array)"
              rows={7}
              value={form.gates}
              disabled={detail.data?.builtin}
              onChange={(e) => setForm({ ...form, gates: e.target.value })}
              placeholder={'[\n  {\n    "name": "has-tools",\n    "phase": "pre",\n    "required": true,\n    "check": "has_tools"\n  }\n]'}
            />
            <Input
              label="Version Note"
              value={form.version_note}
              disabled={detail.data?.builtin}
              onChange={(e) => setForm({ ...form, version_note: e.target.value })}
              placeholder="Reason for the prompt/profile update"
            />
            <p className="text-[12px] leading-6 text-[#1d1d1f]/46">
              `preferred_role` pilote le routage auto cluster. Si tu mets `gpu`, l&apos;orchestration cherchera d&apos;abord un noeud cluster `gpu` compatible avec le provider/modele de cet agent.
            </p>
            <p className="text-[12px] leading-6 text-[#1d1d1f]/46">
              Les champs avancés acceptent des listes CSV et du JSON brut. Les gates sont persistées avec l&apos;agent et réévaluées par le runtime.
            </p>
            {formValidationError ? (
              <InlineNotice title="invalid metadata" message={formValidationError} tone="error" />
            ) : null}
            {saveError ? (
              <InlineNotice title="save failed" message={saveError} tone="error" />
            ) : null}
            <div className="flex justify-between gap-3 pt-2">
              <div>
                {!detail.data?.builtin ? (
                  <Button
                    variant="secondary"
                    onClick={() => setShowDeleteModal(true)}
                    disabled={deleting}
                  >
                    delete agent
                  </Button>
                ) : null}
              </div>
              <div className="flex gap-3">
                <Button variant="secondary" onClick={() => void detail.refetch()}>
                  reload profile
                </Button>
                <Button
                  onClick={handleSave}
                  loading={saving}
                  disabled={!form.system_prompt.trim() || detail.data?.builtin}
                >
                  save profile
                </Button>
              </div>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card title="Message lane">
            <div className="space-y-4">
              <Textarea
                label="Message"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Enter a message for this agent..."
                rows={7}
              />
              {loading ? (
                <LoadingPanel
                  compact
                  title="Running agent"
                  message="The selected agent is processing the current message through the gateway."
                />
              ) : null}
            </div>
          </Card>

          <Card title="Prompt history">
            <div className="space-y-3">
              {(detail.data?.prompt_versions || []).length === 0 ? (
                <p className="text-sm leading-6 text-[#86868b]">
                  No prompt history recorded yet for this agent.
                </p>
              ) : (
                [...(detail.data?.prompt_versions || [])]
                  .sort((left, right) => right.version_number - left.version_number)
                  .map((version) => (
                    <div
                      key={version.version_number}
                      className="rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-2">
                          <div className="flex flex-wrap gap-2">
                            <Badge color="accent">v{version.version_number}</Badge>
                            <Badge color="muted">{formatStamp(version.timestamp)}</Badge>
                            <Badge color="muted">{version.author_hash}</Badge>
                          </div>
                          {version.note ? (
                            <p className="text-sm leading-6 text-[#1d1d1f]/64">{version.note}</p>
                          ) : null}
                        </div>
                        {!detail.data?.builtin ? (
                          <Button
                            variant="secondary"
                            loading={rollbackApi.loading}
                            onClick={() => void handleRollback(version.version_number)}
                          >
                            rollback
                          </Button>
                        ) : null}
                      </div>
                      <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-2xl border border-[rgba(0,0,0,0.06)] bg-white/80 p-3 text-xs leading-6 text-[#1d1d1f]/72">
                        {version.content}
                      </pre>
                    </div>
                  ))
              )}
              {rollbackApi.error ? (
                <InlineNotice title="rollback failed" message={rollbackApi.error} tone="error" />
              ) : null}
            </div>
          </Card>

          {error ? (
            <Card>
              <InlineNotice title="run error" message={error} tone="error" />
            </Card>
          ) : null}

          {result ? (
            <Card title="Response">
              <div className="space-y-4">
                {status === "success" ? (
                  <InlineNotice
                    title="run complete"
                    message={`Agent ${name} returned a response via ${result.provider} on ${result.model}.`}
                    tone="success"
                  />
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Badge color="accent">{result.provider}</Badge>
                  <Badge color="muted">{result.model}</Badge>
                  {result.usage ? (
                    <Badge color="muted">
                      {result.usage.input_tokens} / {result.usage.output_tokens}
                    </Badge>
                  ) : null}
                </div>
                <div className="whitespace-pre-wrap rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4 text-sm leading-7 text-[#1d1d1f]">
                  {result.content}
                </div>
              </div>
            </Card>
          ) : null}
        </div>
      </section>

      <Modal
        open={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        title="Delete Agent"
      >
        <div className="space-y-4">
          <p className="text-sm leading-7 text-[#1d1d1f]">
            Are you sure you want to delete the agent <strong className="text-accent">{name}</strong>? This action cannot be undone.
          </p>
          {deleteError ? (
            <InlineNotice title="delete failed" message={deleteError} tone="error" />
          ) : null}
          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="secondary"
              onClick={() => setShowDeleteModal(false)}
              disabled={deleting}
            >
              cancel
            </Button>
            <Button onClick={handleDelete} loading={deleting}>
              delete agent
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
