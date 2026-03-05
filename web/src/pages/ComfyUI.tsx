import { useState } from "react";
import { comfyuiApi } from "../api/comfyui";
import { useFetch } from "../hooks/useFetch";
import { useApi } from "../hooks/useApi";
import { Card, Button, Input, Spinner } from "../components/ui";

export default function ComfyUI() {
  const status = useFetch<Record<string, unknown>>("/api/comfyui/status");
  const queue = useFetch<Record<string, unknown>>("/api/comfyui/queue");
  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState("");
  const generate = useApi(() =>
    comfyuiApi.generate({
      prompt,
      negative_prompt: negative || undefined,
    }),
  );

  if (status.loading) return <Spinner className="mx-auto mt-20" />;

  return (
    <div className="space-y-4">
      <Card title="ComfyUI Status">
        {status.error ? (
          <p className="text-error text-sm">{status.error}</p>
        ) : (
          <pre className="text-xs text-slate-200 whitespace-pre-wrap">
            {JSON.stringify(status.data ?? {}, null, 2)}
          </pre>
        )}
      </Card>

      <Card title="Queue">
        {queue.loading ? (
          <Spinner />
        ) : queue.error ? (
          <p className="text-error text-sm">{queue.error}</p>
        ) : (
          <pre className="text-xs text-slate-200 whitespace-pre-wrap">
            {JSON.stringify(queue.data ?? {}, null, 2)}
          </pre>
        )}
      </Card>

      <Card title="Generate Image">
        <div className="space-y-3">
          <Input
            label="Prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="A cinematic portrait..."
          />
          <Input
            label="Negative Prompt"
            value={negative}
            onChange={(e) => setNegative(e.target.value)}
            placeholder="blurry, low quality..."
          />
          <Button
            onClick={() => generate.execute(undefined)}
            loading={generate.loading}
            disabled={!prompt.trim()}
          >
            Generate
          </Button>
          {generate.error && <p className="text-error text-sm">{generate.error}</p>}
          {generate.data && (
            <pre className="text-xs text-slate-200 whitespace-pre-wrap">
              {JSON.stringify(generate.data, null, 2)}
            </pre>
          )}
        </div>
      </Card>
    </div>
  );
}

