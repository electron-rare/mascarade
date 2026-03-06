import { useCallback, useMemo, useState } from "react";
import { agentsApi } from "../api/agents";
import { useFetch } from "../hooks/useFetch";
import { useApi } from "../hooks/useApi";
import {
  Badge,
  Button,
  Card,
  InlineNotice,
  Input,
  JsonView,
  LoadingPanel,
  Select,
  Textarea,
} from "../components/ui";

const strategies = [
  { value: "", label: "Default" },
  { value: "cheapest", label: "Cheapest" },
  { value: "fastest", label: "Fastest" },
  { value: "best", label: "Best" },
];

export default function Playground() {
  const [prompt, setPrompt] = useState("");
  const [system, setSystem] = useState("");
  const [strategy, setStrategy] = useState("");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [temperature, setTemperature] = useState("0.7");

  const {
    data: providerData,
    loading: providersLoading,
    error: providersError,
    refetch: refetchProviders,
  } = useFetch<{ providers: string[] }>("/api/agents/providers");
  const providers = providerData?.providers || [];

  const sendFn = useCallback(
    () =>
      agentsApi.send({
        messages: [{ role: "user", content: prompt }],
        ...(strategy && { strategy }),
        ...(provider && { provider }),
        ...(model && { model }),
        ...(system && { system }),
        temperature: parseFloat(temperature) || 0.7,
      }),
    [prompt, strategy, provider, model, system, temperature],
  );

  const { execute, data: result, loading, error, status } = useApi(sendFn);
  const tokenSummary = useMemo(() => {
    if (!result?.usage) return null;
    return `${result.usage.input_tokens} in / ${result.usage.output_tokens} out`;
  }, [result]);

  const handleSend = () => {
    if (!prompt.trim()) return;
    void execute(undefined);
  };

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(9,14,11,0.9)_26%,rgba(7,7,7,0.95))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">prompt lane</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                Direct routing sandbox
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Cette surface sert a tester rapidement un prompt, imposer un provider ou un modele,
                puis lire la reponse brute du core sans quitter le cockpit.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                  providers {providers.length}
                </span>
                <span className="status-chip border-border/80 bg-black/25 text-muted">
                  strategy {strategy || "default"}
                </span>
                <span className="status-chip border-border/80 bg-black/25 text-muted">
                  temp {temperature}
                </span>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-3 lg:min-w-[340px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">prompt</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {prompt.trim() ? "armed" : "idle"}
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">provider</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {provider || "auto"}
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">response</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {result ? "loaded" : "waiting"}
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Dispatch Settings">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/58">
              Fixer ici le mode de routage avant d&apos;envoyer le prompt dans la lane de test.
            </p>
            {providersLoading && !providerData ? (
              <LoadingPanel
                compact
                title="Syncing providers"
                message="Collecting the provider bus exposed by the gateway."
              />
            ) : providersError && !providerData ? (
              <InlineNotice
                title="provider bus unavailable"
                message={providersError}
                tone="error"
                action={
                  <Button variant="ghost" onClick={() => void refetchProviders()}>
                    retry provider sync
                  </Button>
                }
              />
            ) : (
              <div className="rounded-[1.5rem] border border-border/80 bg-black/25 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="screen-label">provider bus</p>
                  <span className="status-chip border-border/80 bg-black/30 text-muted">
                    {providers.length} live
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-amber-100/58">
                  {providers.length > 0
                    ? `${providers.length} provider(s) disponibles pour le routage manuel ou auto.`
                    : "No providers detected on the gateway. Auto routing stays constrained until the bus comes back."}
                </p>
                {providers.length === 0 ? (
                  <div className="mt-4">
                    <Button variant="secondary" onClick={() => void refetchProviders()}>
                      refresh providers
                    </Button>
                  </div>
                ) : null}
              </div>
            )}
            <Select
              label="Strategy"
              options={strategies}
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
            />
            <Select
              label="Provider"
              options={[
                { value: "", label: "Auto" },
                ...providers.map((p) => ({ value: p, label: p })),
              ]}
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              disabled={providersLoading && providers.length === 0}
            />
            <Input
              label="Model Override"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="e.g. mistral-large-latest"
            />
            <Input
              label="Temperature"
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={temperature}
              onChange={(e) => setTemperature(e.target.value)}
            />
          </div>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Card title="Prompt Composer">
          <div className="space-y-4">
            <Textarea
              label="System Prompt"
              value={system}
              onChange={(e) => setSystem(e.target.value)}
              placeholder="Define the operator posture, constraints or output schema."
              rows={4}
            />
            <Textarea
              label="User Message"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Enter the prompt you want to route through Mascarade."
              rows={8}
            />
            <div className="flex flex-wrap gap-3">
              <Button onClick={handleSend} loading={loading} disabled={!prompt.trim()}>
                send prompt
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setPrompt("");
                  setSystem("");
                }}
                disabled={!prompt && !system}
              >
                clear draft
              </Button>
            </div>
          </div>
        </Card>

        <Card title="Response Lane">
          {loading ? (
            <LoadingPanel
              compact
              title="Routing prompt"
              message="Waiting for the gateway to pick a provider and return the first response."
            />
          ) : error ? (
            <InlineNotice
              title="dispatch error"
              message={error}
              tone="error"
            />
          ) : result ? (
            <div className="space-y-3">
              {status === "success" ? (
                <InlineNotice
                  title="dispatch complete"
                  message={`Response returned by ${result.provider} on ${result.model}.`}
                  tone="success"
                />
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Badge color="accent">{result.provider}</Badge>
                <Badge color="muted">{result.model}</Badge>
                {tokenSummary ? <Badge color="muted">{tokenSummary}</Badge> : null}
              </div>
              <div className="whitespace-pre-wrap rounded-[1.5rem] border border-border/80 bg-black/25 p-4 text-sm leading-7 text-amber-100/78">
                {result.content}
              </div>
            </div>
          ) : (
            <p className="text-sm leading-7 text-amber-100/54">
              No response yet. Send a prompt to inspect the provider decision and payload.
            </p>
          )}
        </Card>

        <Card title="Raw Payload">
          {loading ? (
            <LoadingPanel
              compact
              title="Payload pending"
              message="The raw JSON payload will land here as soon as the dispatch returns."
            />
          ) : result ? (
            <JsonView data={result} />
          ) : (
            <p className="text-sm leading-7 text-amber-100/54">
              The raw JSON response will appear here after the next call.
            </p>
          )}
        </Card>
      </section>
    </div>
  );
}
