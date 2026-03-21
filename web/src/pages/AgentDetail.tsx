import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { agentsApi, type Agent, type AgentMetrics } from "../api/agents";
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
};

function normalizeOptional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
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
    });
  }, [detail.data]);

  const runFn = useCallback(
    () => agentsApi.run(name!, [{ role: "user", content: input }]),
    [name, input],
  );

  const updateFn = useMemo(
    () => () =>
      agentsApi.update(name!, {
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
    [form, name],
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

  const handleRun = () => {
    if (!input.trim()) return;
    void execute(undefined);
  };

  const handleSave = async () => {
    if (!name || !form.system_prompt.trim() || detail.data?.builtin) return;
    const updated = await saveProfile(undefined);
    if (updated) {
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
              <p className="screen-label">agent focus</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                {name}
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
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
            <p className="text-sm leading-7 text-amber-100/58">
              Lance un test direct, puis ajuste le profil de routage si l&apos;agent doit preferer un noeud `gpu`, `edge` ou un provider/modele donne.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button onClick={handleRun} loading={loading} disabled={!input.trim()}>
                run agent
              </Button>
              <Link
                to="/orchestrate"
                className="rounded-2xl border border-border/80 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/72 transition hover:border-accent/35 hover:text-accent"
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
                <p className="screen-label">performance track</p>
                <p className="mt-3 text-sm leading-6 text-amber-100/54">
                  Metriques de sante et d&apos;activite pour {name}. Les compteurs remontent depuis le core tracker du registry.
                </p>
              </div>
              <span
                className={[
                  "status-chip",
                  healthStatusOk(metrics.data.error_rate)
                    ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"
                    : "border-[#5d2332] bg-[#18070d]/80 text-error",
                ].join(" ")}
              >
                {healthStatusText(metrics.data.error_rate)}
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">requests</p>
                <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                  {metrics.data.total_requests.toString().padStart(2, "0")}
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">error rate</p>
                <p
                  className={[
                    "mt-3 text-xl font-semibold uppercase tracking-[0.14em]",
                    healthStatusOk(metrics.data.error_rate) ? "text-[#8cffb7]" : "text-error",
                  ].join(" ")}
                >
                  {metrics.data.error_rate.toFixed(1)}%
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">latency</p>
                <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                  {metrics.data.avg_response_time > 0
                    ? `${Math.round(metrics.data.avg_response_time)} ms`
                    : "-"}
                </p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">tokens</p>
                <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                  {metrics.data.total_tokens.toLocaleString()}
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                <p className="text-[10px] uppercase tracking-[0.18em] text-muted">cost</p>
                <p className="mt-3 text-xl font-semibold uppercase tracking-[0.14em] text-accent">
                  ${metrics.data.total_cost.toFixed(4)}
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
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
            <p className="text-[12px] leading-6 text-amber-100/46">
              `preferred_role` pilote le routage auto cluster. Si tu mets `gpu`, l&apos;orchestration cherchera d&apos;abord un noeud cluster `gpu` compatible avec le provider/modele de cet agent.
            </p>
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
                <div className="whitespace-pre-wrap rounded-[1.5rem] border border-border/80 bg-black/25 p-4 text-sm leading-7 text-amber-100/78">
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
          <p className="text-sm leading-7 text-amber-100/78">
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
