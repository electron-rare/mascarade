import { useState } from "react";
import { Link } from "react-router-dom";
import { agentsApi, Agent } from "../api/agents";
import { useApi } from "../hooks/useApi";
import { useFetch } from "../hooks/useFetch";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  InlineNotice,
  Input,
  LoadingPanel,
  Modal,
  Textarea,
} from "../components/ui";

export default function Agents() {
  const { data, loading, error, refetch } = useFetch<{ agents: Agent[] }>("/api/agents");
  const [showCreate, setShowCreate] = useState(false);
  const [createdName, setCreatedName] = useState("");
  const [form, setForm] = useState({
    name: "",
    description: "",
    system_prompt: "",
  });

  const {
    execute: create,
    loading: creating,
    error: createError,
    status: createStatus,
  } = useApi(() => agentsApi.create(form));

  const handleCreate = async () => {
    if (!form.name || !form.system_prompt) return;
    const currentName = form.name;
    const created = await create(undefined);
    if (!created) {
      return;
    }
    setCreatedName(currentName);
    setShowCreate(false);
    setForm({ name: "", description: "", system_prompt: "" });
    void refetch();
  };

  if (loading && !data) {
    return (
      <LoadingPanel
        title="Loading registry"
        message="Collecting the agent inventory from the gateway."
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

  const agents = data?.agents || [];

  return (
    <div className="space-y-6">
      {createStatus === "success" && createdName ? (
        <InlineNotice
          title="agent created"
          message={`Registry updated with ${createdName}. The lane can now be opened from the grid below.`}
          tone="success"
        />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.8fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">agent registry</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                Registry and dispatch surfaces
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Chaque agent expose une surface specialisee. Cette vue sert a lire rapidement
                l&apos;inventaire, verifier la densite du registre et ouvrir un agent en detail.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                  agents {agents.length}
                </span>
                <span className="status-chip border-border/80 bg-black/25 text-muted">
                  create {showCreate ? "open" : "ready"}
                </span>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">registry size</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {agents.length.toString().padStart(2, "0")}
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">creation lane</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  live
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Registry Controls">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/58">
              Ouvrir un agent pour le test detaille ou creer une nouvelle surface specialisee.
            </p>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => setShowCreate(true)}>new agent</Button>
              <Button variant="secondary" onClick={() => void refetch()}>
                refresh registry
              </Button>
            </div>
          </div>
        </Card>
      </section>

      {agents.length === 0 ? (
        <EmptyState
          message="No agents registered yet."
          action={<Button onClick={() => setShowCreate(true)}>create one</Button>}
        />
      ) : (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {agents.map((a) => (
            <Link key={a.name} to={`/agents/${a.name}`}>
              <Card className="h-full cursor-pointer transition-colors hover:border-accent/35">
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="screen-label">agent</p>
                      <h3 className="mt-3 text-lg font-semibold uppercase tracking-[0.12em] text-accent">
                        {a.name}
                      </h3>
                    </div>
                    <Badge color="accent">ready</Badge>
                  </div>
                  <p className="text-sm leading-7 text-amber-100/56">
                    {a.description || "No description provided for this registry entry."}
                  </p>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-amber-100/34">
                    open detail
                  </p>
                </div>
              </Card>
            </Link>
          ))}
        </section>
      )}

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Create Agent">
        <div className="space-y-4">
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
            onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
            placeholder="You are..."
            rows={6}
          />
          {createError ? (
            <InlineNotice title="create failed" message={createError} tone="error" />
          ) : null}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setShowCreate(false)}>
              cancel
            </Button>
            <Button onClick={handleCreate} loading={creating} disabled={!form.name || !form.system_prompt}>
              create
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
