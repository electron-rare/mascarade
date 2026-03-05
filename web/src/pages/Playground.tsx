import { useState, useCallback } from "react";
import { agentsApi } from "../api/agents";
import { useFetch } from "../hooks/useFetch";
import { useApi } from "../hooks/useApi";
import {
  Card,
  Button,
  Textarea,
  Select,
  Input,
  JsonView,
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

  const { data: providerData } = useFetch<{ providers: string[] }>(
    "/api/agents/providers",
  );
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

  const { execute, data: result, loading, error } = useApi(sendFn);

  const handleSend = () => {
    if (!prompt.trim()) return;
    execute(undefined);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <div className="lg:col-span-2 space-y-4">
        <Card title="Prompt">
          <div className="space-y-3">
            <Textarea
              label="System prompt (optional)"
              value={system}
              onChange={(e) => setSystem(e.target.value)}
              placeholder="You are a helpful assistant..."
              rows={2}
            />
            <Textarea
              label="User message"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Enter your prompt..."
              rows={5}
            />
            <Button onClick={handleSend} loading={loading} disabled={!prompt.trim()}>
              Send
            </Button>
          </div>
        </Card>

        {error && (
          <Card>
            <p className="text-error text-sm">{error}</p>
          </Card>
        )}

        {result && (
          <Card title="Response">
            <div className="space-y-3">
              <div className="prose prose-invert text-sm text-slate-300 whitespace-pre-wrap">
                {result.content}
              </div>
              <div className="flex gap-3 text-xs text-muted pt-2 border-t border-border">
                <span>Provider: {result.provider}</span>
                <span>Model: {result.model}</span>
                {result.usage && (
                  <span>
                    Tokens: {result.usage.input_tokens} in /{" "}
                    {result.usage.output_tokens} out
                  </span>
                )}
              </div>
            </div>
          </Card>
        )}
      </div>

      <div className="space-y-4">
        <Card title="Settings">
          <div className="space-y-3">
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
            />
            <Input
              label="Model (optional)"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="e.g. gpt-4o"
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

        {result && (
          <Card title="Raw Response">
            <JsonView data={result} />
          </Card>
        )}
      </div>
    </div>
  );
}
