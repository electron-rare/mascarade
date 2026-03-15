import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import "@xyflow/react/dist/style.css";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  type Node,
  type Edge
} from "@xyflow/react";
import {
  killLifeApi,
  type KillLifeEvidenceEntry,
  type KillLifeRunRecord,
  type KillLifeValidation,
  type KillLifeWorkflow,
  type KillLifeWorkflowNode,
} from "../api/killlife";
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

const nodePalette = [
  { type: "note", label: "Note" },
  { type: "manual-gate", label: "Manual Gate" },
  { type: "local-action", label: "Local Action" },
  { type: "github-dispatch", label: "GitHub Dispatch" },
];

const nodeTypeOptions = nodePalette.map((entry) => ({ value: entry.type, label: entry.label }));

const workflowStatusOptions = [
  { value: "draft", label: "Draft" },
  { value: "ready", label: "Ready" },
  { value: "archived", label: "Archived" },
];

const localActionOptions = [
  { value: "compliance.validate", label: "Compliance Validate" },
  { value: "ci.audit", label: "CI Audit" },
  { value: "firmware.build.esp", label: "Build ESP" },
  { value: "firmware.test.linux", label: "Test Linux" },
  { value: "evidence.collect", label: "Collect Evidence" },
  { value: "evidence.verify", label: "Verify Evidence" },
];

const githubWorkflowOptions = [
  { value: "release_signing.yml", label: "release_signing.yml" },
  { value: "evidence_pack.yml", label: "evidence_pack.yml" },
  { value: "repo_state.yml", label: "repo_state.yml" },
  { value: "static.yml", label: "static.yml" },
  { value: "badges.yml", label: "badges.yml" },
];

function cloneWorkflow<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function durationLabel(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function statusColor(status: string): "accent" | "warning" | "error" | "muted" {
  if (status === "success" || status === "ready") return "accent";
  if (status === "draft" || status === "dry-run") return "warning";
  if (status === "failed" || status === "archived") return "error";
  return "muted";
}

function defaultRunner(type: string) {
  if (type === "local-action") {
    return { kind: "local-action", action: "compliance.validate" };
  }
  if (type === "github-dispatch") {
    return {
      kind: "github-dispatch",
      workflow_file: "release_signing.yml",
      ref: "main",
      inputs: { source: "mascarade-kill-life-editor" },
    };
  }
  return { kind: "none" };
}

function nextNodeId(workflow: KillLifeWorkflow, prefix: string): string {
  const safePrefix = prefix.replace(/[^a-z0-9]+/gi, "-").replace(/^-+|-+$/g, "").toLowerCase() || "node";
  let index = workflow.nodes.length + 1;
  while (workflow.nodes.some((node) => node.id === `${safePrefix}-${index}`)) {
    index += 1;
  }
  return `${safePrefix}-${index}`;
}

function nextEdgeId(workflow: KillLifeWorkflow, source: string, target: string): string {
  const base = `${source}-${target}`.replace(/[^a-z0-9._-]/gi, "-");
  let candidate = base;
  let index = 1;
  while (workflow.edges.some((edge) => edge.id === candidate)) {
    index += 1;
    candidate = `${base}-${index}`;
  }
  return candidate;
}

function autoLayout(workflow: KillLifeWorkflow): KillLifeWorkflow {
  const next = cloneWorkflow(workflow);
  const adjacency = new Map<string, string[]>();
  const indegree = new Map<string, number>();
  for (const node of next.nodes) {
    adjacency.set(node.id, []);
    indegree.set(node.id, 0);
  }
  for (const edge of next.edges) {
    adjacency.get(edge.source)?.push(edge.target);
    indegree.set(edge.target, (indegree.get(edge.target) || 0) + 1);
  }
  const levels = new Map<string, number>();
  const queue = next.nodes
    .filter((node) => (indegree.get(node.id) || 0) === 0)
    .map((node) => node.id);
  for (const root of queue) levels.set(root, 0);

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) continue;
    const level = levels.get(current) || 0;
    for (const target of adjacency.get(current) || []) {
      levels.set(target, Math.max(levels.get(target) || 0, level + 1));
      indegree.set(target, (indegree.get(target) || 0) - 1);
      if ((indegree.get(target) || 0) === 0) {
        queue.push(target);
      }
    }
  }

  const columns = new Map<number, KillLifeWorkflowNode[]>();
  for (const node of next.nodes) {
    const level = levels.get(node.id) || 0;
    const bucket = columns.get(level) || [];
    bucket.push(node);
    columns.set(level, bucket);
  }

  for (const [level, nodes] of columns.entries()) {
    nodes
      .sort((left, right) => left.label.localeCompare(right.label))
      .forEach((node, index) => {
        node.x = 80 + level * 280;
        node.y = 100 + index * 180;
      });
  }
  return next;
}

export function NoteNode({ data }: { data: KillLifeWorkflowNode }) {
  return (
    <div className="relative flex w-[220px] flex-col rounded-[1.3rem] border border-border/80 bg-black/30 p-4">
      <Handle type="target" position={Position.Left} />

      <span className="text-[10px] uppercase tracking-[0.2em] text-muted">{data.type}</span>
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-amber-100">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-amber-100/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-amber-100/40">
        visual node
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export function GroupNode({ data }: { data: KillLifeWorkflowNode }) {
  return (
    <div className="relative flex w-[220px] flex-col rounded-[1.3rem] border border-border/80 bg-black/30 p-4">
      <Handle type="target" position={Position.Left} />

      <span className="text-[10px] uppercase tracking-[0.2em] text-muted">{data.type}</span>
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-amber-100">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-amber-100/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-amber-100/40">
        group container
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export function DecisionNode({ data }: { data: KillLifeWorkflowNode }) {
  return (
    <div className="relative flex w-[220px] flex-col rounded-[1.3rem] border border-border/80 bg-black/30 p-4">
      <Handle type="target" position={Position.Left} />

      <span className="text-[10px] uppercase tracking-[0.2em] text-muted">{data.type}</span>
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-amber-100">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-amber-100/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-amber-100/40">
        decision point
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export function ManualGateNode({ data }: { data: KillLifeWorkflowNode }) {
  return (
    <div className="relative flex w-[220px] flex-col rounded-[1.3rem] border border-border/80 bg-black/30 p-4">
      <Handle type="target" position={Position.Left} />

      <span className="text-[10px] uppercase tracking-[0.2em] text-muted">{data.type}</span>
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-amber-100">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-amber-100/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-amber-100/40">
        manual approval
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export function LocalActionNode({ data }: { data: KillLifeWorkflowNode }) {
  return (
    <div className="relative flex w-[220px] flex-col rounded-[1.3rem] border border-accent/28 bg-black/35 p-4">
      <Handle type="target" position={Position.Left} />

      <span className="text-[10px] uppercase tracking-[0.2em] text-muted">{data.type}</span>
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-amber-100">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-amber-100/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-amber-100/40">
        {data.runner?.kind === "local-action" ? data.runner.action : "local action"}
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export function GithubDispatchNode({ data }: { data: KillLifeWorkflowNode }) {
  return (
    <div className="relative flex w-[220px] flex-col rounded-[1.3rem] border border-[#8cffb7]/35 bg-[#07140c]/80 p-4">
      <Handle type="target" position={Position.Left} />

      <span className="text-[10px] uppercase tracking-[0.2em] text-muted">{data.type}</span>
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-amber-100">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-amber-100/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-amber-100/40">
        {data.runner?.kind === "github-dispatch" ? data.runner.workflow_file : "github dispatch"}
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

// ReactFlow node type mapping - defined outside component to prevent re-renders
const nodeTypes = {
  "note": NoteNode,
  "manual-gate": ManualGateNode,
  "local-action": LocalActionNode,
  "github-dispatch": GithubDispatchNode,
};
// Will be used in ReactFlow integration
void nodeTypes;
void ReactFlow;

export default function KillLifeWorkflowEditor() {
  const { workflowId = "" } = useParams();
  const details = useFetch<{
    workflow: KillLifeWorkflow;
    validation: KillLifeValidation;
    runs: KillLifeRunRecord[];
  }>(workflowId ? `/api/killlife/workflows/${encodeURIComponent(workflowId)}` : null);

  const [workflow, setWorkflow] = useState<KillLifeWorkflow | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [linkSourceId, setLinkSourceId] = useState<string | null>(null);
  const [validation, setValidation] = useState<KillLifeValidation | null>(null);
  const [dirty, setDirty] = useState(false);
  const [configText, setConfigText] = useState("{}");
  const [runnerInputsText, setRunnerInputsText] = useState("{}");
  const [edgeTargetId, setEdgeTargetId] = useState("");

  const saveAction = useApi(async (doc: KillLifeWorkflow) => killLifeApi.save(doc.id, doc));
  const validateAction = useApi(async (doc: KillLifeWorkflow) => killLifeApi.validate(doc.id, doc));
  const runAction = useApi(
    async (args: { mode: "local" | "github"; dry_run?: boolean }) =>
      killLifeApi.run(workflowId, args),
  );

  useEffect(() => {
    if (!details.data?.workflow) return;
    const next = cloneWorkflow(details.data.workflow);
    setWorkflow(next);
    setValidation(details.data.validation);
    setSelectedNodeId((current) => current && next.nodes.some((node) => node.id === current) ? current : next.nodes[0]?.id || null);
    setDirty(false);
  }, [details.data?.workflow, details.data?.validation]);

  const selectedNode = useMemo(
    () => workflow?.nodes.find((node) => node.id === selectedNodeId) || null,
    [selectedNodeId, workflow],
  );

  const reactFlowNodesInitial = useMemo<Node<KillLifeWorkflowNode>[]>(() => {
    if (!workflow) return [];
    return workflow.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      position: { x: node.x, y: node.y },
      data: node,
    }));
  }, [workflow]);

  const reactFlowEdgesInitial = useMemo<Edge[]>(() => {
    if (!workflow) return [];
    return workflow.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
    }));
  }, [workflow]);

  const [nodes, setNodes, onNodesChange] = useNodesState(reactFlowNodesInitial);
  const [edges, setEdges, onEdgesChange] = useEdgesState(reactFlowEdgesInitial);

  // Sync ReactFlow state when workflow changes
  useEffect(() => {
    setNodes(reactFlowNodesInitial);
    setEdges(reactFlowEdgesInitial);
  }, [reactFlowNodesInitial, reactFlowEdgesInitial, setNodes, setEdges]);

  useEffect(() => {
    setConfigText(JSON.stringify(selectedNode?.config || {}, null, 2));
    setRunnerInputsText(JSON.stringify(selectedNode?.runner?.inputs || {}, null, 2));
    setEdgeTargetId("");
  }, [selectedNode?.id]);

  const evidenceTarget =
    selectedNode && typeof selectedNode.config?.target === "string" ? selectedNode.config.target : null;
  const evidence = useFetch<{ evidence: KillLifeEvidenceEntry[] }>(
    evidenceTarget ? `/api/killlife/evidence/${encodeURIComponent(evidenceTarget)}` : null,
  );

  const displayedRuns = useMemo(() => {
    const base = details.data?.runs ?? [];
    if (!runAction.data) return base;
    return [runAction.data, ...base.filter((run) => run.run_id !== runAction.data?.run_id)];
  }, [details.data?.runs, runAction.data]);

  const handleWorkflowField = (field: keyof KillLifeWorkflow, value: string | string[]) => {
    setWorkflow((current) => {
      if (!current) return current;
      const next = cloneWorkflow(current);
      (next as Record<string, unknown>)[field] = value;
      return next;
    });
    setDirty(true);
  };

  const updateNode = (nodeId: string, updater: (node: KillLifeWorkflowNode) => void) => {
    setWorkflow((current) => {
      if (!current) return current;
      const next = cloneWorkflow(current);
      const node = next.nodes.find((entry) => entry.id === nodeId);
      if (!node) return current;
      updater(node);
      return next;
    });
    setDirty(true);
  };

  const addNode = (type: string) => {
    setWorkflow((current) => {
      if (!current) return current;
      const next = cloneWorkflow(current);
      const label = nodePalette.find((entry) => entry.type === type)?.label || "Node";
      const nodeId = nextNodeId(next, type);
      next.nodes.push({
        id: nodeId,
        type,
        label,
        description: "",
        x: 80 + (next.nodes.length % 4) * 250,
        y: 120 + Math.floor(next.nodes.length / 4) * 160,
        runner: defaultRunner(type),
        config: type === "local-action" ? {} : {},
      });
      setSelectedNodeId(nodeId);
      return next;
    });
    setDirty(true);
  };

  const removeSelectedNode = () => {
    if (!selectedNode || !workflow) return;
    setWorkflow((current) => {
      if (!current) return current;
      const next = cloneWorkflow(current);
      next.nodes = next.nodes.filter((node) => node.id !== selectedNode.id);
      next.edges = next.edges.filter((edge) => edge.source !== selectedNode.id && edge.target !== selectedNode.id);
      return next;
    });
    setSelectedNodeId(null);
    setLinkSourceId(null);
    setDirty(true);
  };

  const connectNodes = (sourceId: string, targetId: string) => {
    if (!workflow || sourceId === targetId) return;
    if (workflow.edges.some((edge) => edge.source === sourceId && edge.target === targetId)) return;
    setWorkflow((current) => {
      if (!current) return current;
      const next = cloneWorkflow(current);
      next.edges.push({
        id: nextEdgeId(next, sourceId, targetId),
        source: sourceId,
        target: targetId,
      });
      return next;
    });
    setDirty(true);
  };

  const removeEdge = (edgeId: string) => {
    setWorkflow((current) => {
      if (!current) return current;
      const next = cloneWorkflow(current);
      next.edges = next.edges.filter((edge) => edge.id !== edgeId);
      return next;
    });
    setDirty(true);
  };

  const applyConfigJson = () => {
    if (!selectedNode) return;
    try {
      const parsed = JSON.parse(configText) as Record<string, unknown>;
      updateNode(selectedNode.id, (node) => {
        node.config = parsed;
      });
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Invalid JSON");
    }
  };

  const applyRunnerInputsJson = () => {
    if (!selectedNode) return;
    try {
      const parsed = JSON.parse(runnerInputsText) as Record<string, unknown>;
      updateNode(selectedNode.id, (node) => {
        node.runner = {
          ...(node.runner || {}),
          inputs: parsed,
        };
      });
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Invalid JSON");
    }
  };

  const handleValidate = async () => {
    if (!workflow) return;
    const result = await validateAction.execute(workflow);
    if (result) {
      setValidation(result);
    }
  };

  const handleSave = async () => {
    if (!workflow) return;
    const result = await saveAction.execute(workflow);
    if (!result) return;
    setWorkflow(cloneWorkflow(result.workflow));
    setValidation(result.validation);
    setDirty(false);
    await details.refetch();
  };

  const handleRun = async (mode: "local" | "github", dryRun?: boolean) => {
    const result = await runAction.execute({ mode, dry_run: dryRun });
    if (!result) return;
    await details.refetch();
  };

  const outgoingEdges = workflow?.edges.filter((edge) => edge.source === selectedNodeId) || [];

  if (details.loading && !details.data) {
    return (
      <LoadingPanel
        title="Opening Kill_LIFE editor"
        message="Loading workflow graph, validation state and the latest run records."
      />
    );
  }

  if (details.error && !details.data) {
    return (
      <InlineNotice
        title="workflow load error"
        message={details.error}
        tone="error"
        className="mx-auto mt-20 max-w-3xl"
      />
    );
  }

  if (!workflow) {
    return <EmptyState message="No workflow loaded." action={<Link to="/kill-life">Back to registry</Link>} />;
  }

  return (
    <div className="space-y-6" data-shortcuts-lock="true">
      {saveAction.error ? <InlineNotice title="save error" message={saveAction.error} tone="error" /> : null}
      {validateAction.error ? <InlineNotice title="validation error" message={validateAction.error} tone="error" /> : null}
      {runAction.error ? <InlineNotice title="run error" message={runAction.error} tone="error" /> : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(340px,0.85fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">graph editor</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                {workflow.title}
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Canvas graphique éditable: ajoute des nœuds, relie-les visuellement, déplace-les à la souris, puis valide et lance les runs locaux ou GitHub depuis Mascarade.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <Badge color={dirty ? "warning" : "accent"}>{dirty ? "dirty" : "saved"}</Badge>
                <Badge color={statusColor(workflow.status)}>{workflow.status}</Badge>
                {workflow.execution_modes.map((mode) => (
                  <Badge key={mode} color="muted">
                    {mode}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">graph</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {workflow.nodes.length.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Nodes / {workflow.edges.length} edges
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">latest run</p>
                <p className="mt-3 text-sm leading-6 text-amber-100/78">
                  {displayedRuns[0] ? `${displayedRuns[0].mode} / ${displayedRuns[0].status}` : "none"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  {displayedRuns[0] ? formatDate(displayedRuns[0].finished_at) : "No run recorded yet"}
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Workflow controls">
          <div className="space-y-4">
            <Input
              label="Title"
              value={workflow.title}
              onChange={(event) => handleWorkflowField("title", event.target.value)}
            />
            <Input
              label="Category"
              value={workflow.category}
              onChange={(event) => handleWorkflowField("category", event.target.value)}
            />
            <Textarea
              label="Description"
              value={workflow.description || ""}
              onChange={(event) => handleWorkflowField("description", event.target.value)}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Select
                label="Status"
                value={workflow.status}
                onChange={(event) => handleWorkflowField("status", event.target.value)}
                options={workflowStatusOptions}
              />
              <Input
                label="Tags"
                value={(workflow.tags || []).join(", ")}
                onChange={(event) =>
                  handleWorkflowField(
                    "tags",
                    event.target.value
                      .split(",")
                      .map((entry) => entry.trim())
                      .filter(Boolean),
                  )
                }
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="Viewport Width"
                type="number"
                value={String(workflow.viewport.width)}
                onChange={(event) =>
                  setWorkflow((current) => {
                    if (!current) return current;
                    const next = cloneWorkflow(current);
                    next.viewport.width = Number(event.target.value) || next.viewport.width;
                    setDirty(true);
                    return next;
                  })
                }
              />
              <Input
                label="Viewport Height"
                type="number"
                value={String(workflow.viewport.height)}
                onChange={(event) =>
                  setWorkflow((current) => {
                    if (!current) return current;
                    const next = cloneWorkflow(current);
                    next.viewport.height = Number(event.target.value) || next.viewport.height;
                    setDirty(true);
                    return next;
                  })
                }
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <Button onClick={handleSave} loading={saveAction.loading}>
                save
              </Button>
              <Button variant="secondary" onClick={handleValidate} loading={validateAction.loading}>
                validate
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setWorkflow((current) => (current ? autoLayout(current) : current));
                  setDirty(true);
                }}
              >
                auto layout
              </Button>
              <Button variant="ghost" onClick={() => void details.refetch()}>
                reload
              </Button>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => void handleRun("local")} loading={runAction.loading}>
                run local
              </Button>
              <Button variant="secondary" onClick={() => void handleRun("github")} loading={runAction.loading}>
                dispatch github
              </Button>
              <Button variant="ghost" onClick={() => void handleRun("local", true)} loading={runAction.loading}>
                dry run
              </Button>
            </div>
          </div>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(380px,0.75fr)]">
        <Card title="Canvas">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {nodePalette.map((entry) => (
                <Button key={entry.type} variant="secondary" onClick={() => addNode(entry.type)}>
                  add {entry.label}
                </Button>
              ))}
              {selectedNode ? (
                <>
                  <Button
                    variant={linkSourceId === selectedNode.id ? "primary" : "ghost"}
                    onClick={() => setLinkSourceId((current) => (current === selectedNode.id ? null : selectedNode.id))}
                  >
                    {linkSourceId === selectedNode.id ? "cancel link" : "link from selected"}
                  </Button>
                  <Button variant="danger" onClick={removeSelectedNode}>
                    delete node
                  </Button>
                </>
              ) : null}
            </div>

            {linkSourceId ? (
              <InlineNotice
                title="link mode"
                message={`Clique un autre nœud du canvas pour créer une liaison depuis '${linkSourceId}'.`}
                tone="info"
              />
            ) : null}

            <div
              className="overflow-hidden rounded-[1.5rem] border border-border/80 bg-black/35"
              style={{ height: "600px" }}
            >
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={(_, node) => {
                  if (linkSourceId && linkSourceId !== node.id) {
                    connectNodes(linkSourceId, node.id);
                    setLinkSourceId(null);
                  } else {
                    setSelectedNodeId(node.id);
                  }
                }}
                nodeTypes={nodeTypes}
                fitView
                className="bg-black/20"
              >
                <Background color="#ffd166" gap={16} size={1} />
                <Controls className="bg-black/60 border-border/80" />
                <MiniMap
                  className="bg-black/60 border border-border/80"
                  nodeColor={(node) => {
                    if (node.type === "local-action") return "rgba(255, 209, 102, 0.5)";
                    if (node.type === "github-dispatch") return "rgba(140, 255, 183, 0.5)";
                    return "rgba(255, 209, 102, 0.3)";
                  }}
                />
              </ReactFlow>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card title="Node inspector">
            {!selectedNode ? (
              <p className="text-sm leading-7 text-amber-100/52">Select a node on the canvas to edit it.</p>
            ) : (
              <div className="space-y-4">
                <Input
                  label="Node Label"
                  value={selectedNode.label}
                  onChange={(event) => updateNode(selectedNode.id, (node) => {
                    node.label = event.target.value;
                  })}
                />
                <Textarea
                  label="Description"
                  value={selectedNode.description || ""}
                  onChange={(event) => updateNode(selectedNode.id, (node) => {
                    node.description = event.target.value;
                  })}
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <Select
                    label="Node Type"
                    value={selectedNode.type}
                    onChange={(event) => updateNode(selectedNode.id, (node) => {
                      node.type = event.target.value;
                      node.runner = defaultRunner(event.target.value);
                    })}
                    options={nodeTypeOptions}
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      label="X"
                      type="number"
                      value={String(Math.round(selectedNode.x))}
                      onChange={(event) => updateNode(selectedNode.id, (node) => {
                        node.x = Number(event.target.value) || 0;
                      })}
                    />
                    <Input
                      label="Y"
                      type="number"
                      value={String(Math.round(selectedNode.y))}
                      onChange={(event) => updateNode(selectedNode.id, (node) => {
                        node.y = Number(event.target.value) || 0;
                      })}
                    />
                  </div>
                </div>

                {selectedNode.type === "local-action" ? (
                  <>
                    <Select
                      label="Local Action"
                      value={selectedNode.runner?.action || "compliance.validate"}
                      onChange={(event) => updateNode(selectedNode.id, (node) => {
                        node.runner = {
                          ...(node.runner || {}),
                          kind: "local-action",
                          action: event.target.value,
                        };
                      })}
                      options={localActionOptions}
                    />
                    {(selectedNode.runner?.action === "evidence.collect" || selectedNode.runner?.action === "evidence.verify") ? (
                      <Input
                        label="Evidence Target"
                        value={typeof selectedNode.config?.target === "string" ? selectedNode.config.target : ""}
                        onChange={(event) => updateNode(selectedNode.id, (node) => {
                          node.config = {
                            ...(node.config || {}),
                            target: event.target.value,
                          };
                        })}
                      />
                    ) : null}
                  </>
                ) : null}

                {selectedNode.type === "github-dispatch" ? (
                  <>
                    <Select
                      label="GitHub Workflow"
                      value={selectedNode.runner?.workflow_file || "release_signing.yml"}
                      onChange={(event) => updateNode(selectedNode.id, (node) => {
                        node.runner = {
                          ...(node.runner || {}),
                          kind: "github-dispatch",
                          workflow_file: event.target.value,
                        };
                      })}
                      options={githubWorkflowOptions}
                    />
                    <Input
                      label="Git Ref"
                      value={selectedNode.runner?.ref || "main"}
                      onChange={(event) => updateNode(selectedNode.id, (node) => {
                        node.runner = {
                          ...(node.runner || {}),
                          kind: "github-dispatch",
                          ref: event.target.value,
                        };
                      })}
                    />
                  </>
                ) : null}

                <Textarea
                  label="Config JSON"
                  value={configText}
                  onChange={(event) => setConfigText(event.target.value)}
                />
                <Button variant="ghost" onClick={applyConfigJson}>
                  apply config json
                </Button>

                {selectedNode.type === "github-dispatch" ? (
                  <>
                    <Textarea
                      label="Runner Inputs JSON"
                      value={runnerInputsText}
                      onChange={(event) => setRunnerInputsText(event.target.value)}
                    />
                    <Button variant="ghost" onClick={applyRunnerInputsJson}>
                      apply runner inputs
                    </Button>
                  </>
                ) : null}

                <div className="space-y-3 rounded-[1.5rem] border border-border/80 bg-black/25 p-4">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-muted">outgoing edges</p>
                  {outgoingEdges.length === 0 ? (
                    <p className="text-sm leading-6 text-amber-100/45">No outgoing edge yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {outgoingEdges.map((edge) => (
                        <div key={edge.id} className="flex items-center justify-between gap-3 rounded-2xl border border-border/70 bg-black/25 px-3 py-2">
                          <span className="text-xs uppercase tracking-[0.16em] text-amber-100/78">
                            {edge.source} → {edge.target}
                          </span>
                          <Button variant="ghost" className="min-h-0 px-3 py-1" onClick={() => removeEdge(edge.id)}>
                            remove
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                    <Select
                      label="Create Edge To"
                      value={edgeTargetId}
                      onChange={(event) => setEdgeTargetId(event.target.value)}
                      options={[
                        { value: "", label: "Select target" },
                        ...workflow.nodes
                          .filter((node) => node.id !== selectedNode.id)
                          .map((node) => ({ value: node.id, label: `${node.label} (${node.id})` })),
                      ]}
                    />
                    <Button
                      className="mt-7"
                      onClick={() => {
                        if (!edgeTargetId) return;
                        connectNodes(selectedNode.id, edgeTargetId);
                        setEdgeTargetId("");
                      }}
                    >
                      add edge
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </Card>

          <Card title="Validation">
            {validation ? (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Badge color={validation.valid ? "accent" : "error"}>
                    {validation.valid ? "valid" : "invalid"}
                  </Badge>
                  <Badge color="muted">schema {validation.schema_errors.length}</Badge>
                  <Badge color="muted">semantic {validation.semantic_errors.length}</Badge>
                  <Badge color="muted">warnings {validation.warnings.length}</Badge>
                </div>

                {validation.schema_errors.length > 0 ? (
                  <InlineNotice
                    title="schema errors"
                    message={validation.schema_errors.join(" | ")}
                    tone="error"
                  />
                ) : null}
                {validation.semantic_errors.length > 0 ? (
                  <InlineNotice
                    title="semantic errors"
                    message={validation.semantic_errors.join(" | ")}
                    tone="error"
                  />
                ) : null}
                {validation.warnings.length > 0 ? (
                  <InlineNotice
                    title="warnings"
                    message={validation.warnings.join(" | ")}
                    tone="info"
                  />
                ) : null}
              </div>
            ) : (
              <p className="text-sm leading-7 text-amber-100/52">Run validation to inspect schema and DAG semantics.</p>
            )}
          </Card>

          <Card title="Evidence + Runs">
            <div className="space-y-4">
              {evidenceTarget ? (
                <>
                  <p className="text-[10px] uppercase tracking-[0.2em] text-muted">
                    evidence target: {evidenceTarget}
                  </p>
                  {evidence.loading && !evidence.data ? (
                    <p className="text-sm leading-6 text-amber-100/45">Loading evidence…</p>
                  ) : evidence.data?.evidence.length ? (
                    <div className="space-y-2">
                      {evidence.data.evidence.map((entry) => (
                        <div key={entry.path} className="rounded-2xl border border-border/70 bg-black/25 px-3 py-2">
                          <p className="text-xs uppercase tracking-[0.16em] text-accent">{entry.path}</p>
                          <p className="mt-1 text-[11px] leading-5 text-amber-100/45">
                            {entry.type} / {entry.size_bytes} bytes / {formatDate(entry.updated_at)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm leading-6 text-amber-100/45">No evidence found for this target.</p>
                  )}
                </>
              ) : (
                <p className="text-sm leading-6 text-amber-100/45">
                  Select an evidence node to inspect the current evidence pack surface.
                </p>
              )}

              <div className="space-y-2">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">recent runs</p>
                {displayedRuns.length === 0 ? (
                  <p className="text-sm leading-6 text-amber-100/45">No run recorded yet.</p>
                ) : (
                  displayedRuns.slice(0, 5).map((run) => (
                    <div key={run.run_id} className="rounded-[1.35rem] border border-border/80 bg-black/25 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-accent">
                            {run.mode} / {run.status}
                          </p>
                          <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                            {formatDate(run.finished_at)} / {run.steps.length} step(s)
                          </p>
                        </div>
                        <Badge color={statusColor(run.status)}>{run.status}</Badge>
                      </div>
                      {run.steps.length > 0 ? (
                        <div className="mt-3 space-y-2">
                          {run.steps.map((step) => (
                            <div key={`${run.run_id}-${step.node_id}`} className="rounded-2xl border border-border/70 bg-black/25 px-3 py-2">
                              <div className="flex flex-wrap items-center justify-between gap-3">
                                <span className="text-[11px] uppercase tracking-[0.16em] text-amber-100/78">
                                  {step.label}
                                </span>
                                <Badge color={statusColor(step.status)}>{step.status}</Badge>
                              </div>
                              <p className="mt-2 text-[11px] leading-5 text-amber-100/45">
                                {step.message || "-"} / {durationLabel(step.duration_ms)}
                              </p>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))
                )}
              </div>
            </div>
          </Card>

          <Card title="Workflow JSON">
            <JsonView data={workflow} />
          </Card>
        </div>
      </section>

      <div className="flex flex-wrap gap-3">
        <Link
          to="/kill-life"
          className="rounded-2xl border border-border/80 bg-black/25 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100/78 transition hover:border-accent/35 hover:text-accent"
        >
          back to registry
        </Link>
      </div>
    </div>
  );
}
