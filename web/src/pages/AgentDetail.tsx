import { useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { agentsApi } from "../api/agents";
import { useApi } from "../hooks/useApi";
import { Card, Button, Textarea, Badge } from "../components/ui";

export default function AgentDetail() {
  const { name } = useParams<{ name: string }>();
  const [input, setInput] = useState("");

  const runFn = useCallback(
    () => agentsApi.run(name!, [{ role: "user", content: input }]),
    [name, input],
  );

  const { execute, data: result, loading, error } = useApi(runFn);

  const handleRun = () => {
    if (!input.trim()) return;
    execute(undefined);
  };

  return (
    <div className="space-y-4 max-w-3xl">
      <Card title={`Agent: ${name}`}>
        <div className="flex gap-2 mb-4">
          <Badge color="accent">{name}</Badge>
        </div>
        <div className="space-y-3">
          <Textarea
            label="Message"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter a message for this agent..."
            rows={4}
          />
          <Button onClick={handleRun} loading={loading} disabled={!input.trim()}>
            Run Agent
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
          <div className="whitespace-pre-wrap text-sm text-slate-300">
            {result.content}
          </div>
          <div className="flex gap-3 text-xs text-muted pt-3 mt-3 border-t border-border">
            <span>Provider: {result.provider}</span>
            <span>Model: {result.model}</span>
            {result.usage && (
              <span>
                Tokens: {result.usage.input_tokens} / {result.usage.output_tokens}
              </span>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
