import { useState } from "react";
import { Link } from "react-router-dom";
import { useFetch } from "../hooks/useFetch";
import { useApi } from "../hooks/useApi";
import { agentsApi, Agent } from "../api/agents";
import {
  Card,
  Button,
  Input,
  Textarea,
  Modal,
  Spinner,
  EmptyState,
} from "../components/ui";

export default function Agents() {
  const { data, loading, error, refetch } = useFetch<{ agents: Agent[] }>(
    "/api/agents",
  );
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    system_prompt: "",
  });

  const { execute: create, loading: creating } = useApi(() =>
    agentsApi.create(form),
  );

  const handleCreate = async () => {
    if (!form.name || !form.system_prompt) return;
    await create(undefined);
    setShowCreate(false);
    setForm({ name: "", description: "", system_prompt: "" });
    refetch();
  };

  if (loading) return <Spinner className="mx-auto mt-20" />;
  if (error) return <p className="text-error text-sm text-center mt-20">{error}</p>;

  const agents = data?.agents || [];

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-muted">{agents.length} agent(s)</p>
        <Button onClick={() => setShowCreate(true)}>New Agent</Button>
      </div>

      {agents.length === 0 ? (
        <EmptyState
          message="No agents registered yet."
          action={<Button onClick={() => setShowCreate(true)}>Create one</Button>}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((a) => (
            <Link key={a.name} to={`/agents/${a.name}`}>
              <Card className="hover:border-accent/40 transition-colors cursor-pointer">
                <h3 className="font-semibold text-sm text-slate-100">
                  {a.name}
                </h3>
                <p className="text-xs text-muted mt-1 line-clamp-2">
                  {a.description || "No description"}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="Create Agent"
      >
        <div className="space-y-3">
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
          <Textarea
            label="System Prompt"
            value={form.system_prompt}
            onChange={(e) =>
              setForm({ ...form, system_prompt: e.target.value })
            }
            placeholder="You are..."
            rows={4}
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              loading={creating}
              disabled={!form.name || !form.system_prompt}
            >
              Create
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
