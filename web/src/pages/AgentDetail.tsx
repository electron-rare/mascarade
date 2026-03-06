import { useCallback, useState } from "react";
import { useParams } from "react-router-dom";
import { agentsApi } from "../api/agents";
import { useApi } from "../hooks/useApi";
import { Badge, Button, Card, InlineNotice, LoadingPanel, Textarea } from "../components/ui";

export default function AgentDetail() {
  const { name } = useParams<{ name: string }>();
  const [input, setInput] = useState("");

  const runFn = useCallback(
    () => agentsApi.run(name!, [{ role: "user", content: input }]),
    [name, input],
  );

  const { execute, data: result, loading, error, status } = useApi(runFn);

  const handleRun = () => {
    if (!input.trim()) return;
    execute(undefined);
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">agent focus</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                {name}
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Surface de test directe pour l&apos;agent selectionne. Ici on injecte un message
                simple et on lit la reponse complete sans orchestration.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge color="accent">{name}</Badge>
              <Badge color="muted">{result ? "responded" : "idle"}</Badge>
            </div>
          </div>
        </Card>

        <Card title="Direct Run">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/58">
              Envoyer un message unique a l&apos;agent courant et lire le couple provider/modele
              qui a repondu.
            </p>
            <Button onClick={handleRun} loading={loading} disabled={!input.trim()}>
              run agent
            </Button>
          </div>
        </Card>
      </section>

      <Card title="Message Lane">
        <div className="space-y-4">
          <Textarea
            label="Message"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter a message for this agent..."
            rows={6}
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
  );
}
