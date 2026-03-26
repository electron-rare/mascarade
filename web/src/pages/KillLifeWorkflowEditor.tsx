import { useEffect, useMemo, useRef, useState } from "react";
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
  type Edge,
  type ReactFlowInstance
} from "@xyflow/react";
import dagre from "dagre";
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

const NODE_WIDTH = 220;
const NODE_HEIGHT = 108;
const MAX_HISTORY_DEPTH = 50;

function applyDagreLayout(nodes: Node[], edges: Edge[]): Node[] {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: 'TB' });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  return nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
    };
  });
}

function autoLayoutDagre(workflow: KillLifeWorkflow): KillLifeWorkflow {
  const next = cloneWorkflow(workflow);

  // Convert to ReactFlow format
  const nodes: Node[] = next.nodes.map((node) => ({
    id: node.id,
    type: node.type,
    position: { x: node.x, y: node.y },
    data: node,
  }));

  const edges: Edge[] = next.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.label,
  }));

  // Apply Dagre layout
  const layoutedNodes = applyDagreLayout(nodes, edges);

  // Update workflow nodes with new positions
  layoutedNodes.forEach((layoutedNode) => {
    const workflowNode = next.nodes.find((n) => n.id === layoutedNode.id);
    if (workflowNode) {
      workflowNode.x = layoutedNode.position.x;
      workflowNode.y = layoutedNode.position.y;
    }
  });

  return next;
}

export function NoteNode({ data }: { data: KillLifeWorkflowNode }) {
  return (
    <div className="relative flex w-[220px] flex-col rounded-[1.3rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
      <Handle type="target" position={Position.Left} />

      <span className="text-[10px] uppercase tracking-[0.2em] text-muted">{data.type}</span>
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-[#1d1d1f]">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-[#1d1d1f]/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-[#1d1d1f]/40">
        visual node
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export function GroupNode({ data }: { data: KillLifeWorkflowNode }) {
  return (
    <div className="relative flex w-[220px] flex-col rounded-[1.3rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
      <Handle type="target" position={Position.Left} />

      <span className="text-[10px] uppercase tracking-[0.2em] text-muted">{data.type}</span>
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-[#1d1d1f]">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-[#1d1d1f]/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-[#1d1d1f]/40">
        group container
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export function DecisionNode({ data }: { data: KillLifeWorkflowNode }) {
  return (
    <div className="relative flex w-[220px] flex-col rounded-[1.3rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
      <Handle type="target" position={Position.Left} />

      <span className="text-[10px] uppercase tracking-[0.2em] text-muted">{data.type}</span>
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-[#1d1d1f]">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-[#1d1d1f]/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-[#1d1d1f]/40">
        decision point
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export function ManualGateNode({ data }: { data: KillLifeWorkflowNode }) {
  return (
    <div className="relative flex w-[220px] flex-col rounded-[1.3rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
      <Handle type="target" position={Position.Left} />

      <span className="text-[10px] uppercase tracking-[0.2em] text-muted">{data.type}</span>
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-[#1d1d1f]">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-[#1d1d1f]/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-[#1d1d1f]/40">
        manual approval
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export function LocalActionNode({ data }: { data: KillLifeWorkflowNode }) {
  return (
    <div className="relative flex w-[220px] flex-col rounded-[1.3rem] border border-accent/28 bg-[#f5f5f7] p-4">
      <Handle type="target" position={Position.Left} />

      <span className="text-[10px] uppercase tracking-[0.2em] text-muted">{data.type}</span>
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-[#1d1d1f]">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-[#1d1d1f]/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-[#1d1d1f]/40">
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
      <span className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-[#1d1d1f]">
        {data.label}
      </span>
      <span className="mt-2 line-clamp-3 text-xs leading-5 text-[#1d1d1f]/56">
        {data.description || "No description"}
      </span>
      <span className="mt-4 text-[10px] uppercase tracking-[0.2em] text-[#1d1d1f]/40">
        {data.runner?.kind === "github-dispatch" ? data.runner.workflow_file : "github dispatch"}
      </span>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

// ReactFlow node type mapping - defined outside component to prevent re-renders
const nodeTypes = {
  "note": NoteNode,
  "group": GroupNode,
  "decision": DecisionNode,
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

  const reactFlowInstance = useRef<ReactFlowInstance<Node<KillLifeWorkflowNode>, Edge> | null>(null);
  const [workflow, setWorkflow] = useState<KillLifeWorkflow | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [linkSourceId, setLinkSourceId] = useState<string | null>(null);
  const [validation, setValidation] = useState<KillLifeValidation | null>(null);
  const [dirty, setDirty] = useState(false);
  const [configText, setConfigText] = useState("{}");
  const [runnerInputsText, setRunnerInputsText] = useState("{}");
  const [edgeTargetId, setEdgeTargetId] = useState("");

  // Undo/Redo state management
  const [historyPast, setHistoryPast] = useState<KillLifeWorkflow[]>([]);
  const [historyFuture, setHistoryFuture] = useState<KillLifeWorkflow[]>([]);

  const saveAction = useApi(async (doc: KillLifeWorkflow) => killLifeApi.save(doc.id, doc));
  const validateAction = useApi(async (doc: KillLifeWorkflow) => killLifeApi.validate(doc.id, doc));
  const runAction = useApi(
    async (args: { mode: "local" | "github"; dry_run?: boolean }) =>
      killLifeApi.run(workflowId, args),
  );

  // Save current workflow state to history before mutation
  const saveSnapshot = () => {
    if (!workflow) return;
    setHistoryPast((past) => {
      const newPast = [...past, cloneWorkflow(workflow)];
      // Limit history to MAX_HISTORY_DEPTH entries to prevent memory issues
      if (newPast.length > MAX_HISTORY_DEPTH) {
        newPast.shift();
      }
      return newPast;
    });
    // Clear future stack when new change is made
    setHistoryFuture([]);
  };

  const undo = () => {
    if (historyPast.length === 0 || !workflow) return;
    const previous = historyPast[historyPast.length - 1];
    setHistoryPast((past) => past.slice(0, -1));
    setHistoryFuture((future) => [cloneWorkflow(workflow), ...future]);
    setWorkflow(cloneWorkflow(previous));
    setDirty(true);
  };

  const redo = () => {
    if (historyFuture.length === 0) return;
    const next = historyFuture[0];
    if (!workflow) return;
    setHistoryFuture((future) => future.slice(1));
    setHistoryPast((past) => [...past, cloneWorkflow(workflow)]);
    setWorkflow(cloneWorkflow(next));
    setDirty(true);
  };

  // Keyboard shortcuts for undo/redo
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'z' && !event.shiftKey) {
        event.preventDefault();
        undo();
      } else if ((event.ctrlKey || event.metaKey) && (event.key === 'y' || (event.key === 'z' && event.shiftKey))) {
        event.preventDefault();
        redo();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [historyPast, historyFuture, workflow]);

  useEffect(() => {
    if (!details.data?.workflow) return;
    const next = cloneWorkflow(details.data.workflow);
    setWorkflow(next);
    setValidation(details.data.validation);
    setSelectedNodeId((current) => current && next.nodes.some((node) => node.id === current) ? current : next.nodes[0]?.id || null);
    setDirty(false);
    // Clear history when loading a new workflow
    setHistoryPast([]);
    setHistoryFuture([]);
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
    saveSnapshot();
    setWorkflow((current) => {
      if (!current) return current;
      const next = cloneWorkflow(current);
      (next as Record<string, unknown>)[field] = value;
      return next;
    });
    setDirty(true);
  };

  const updateNode = (nodeId: string, updater: (node: KillLifeWorkflowNode) => void) => {
    saveSnapshot();
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
    saveSnapshot();
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
    saveSnapshot();
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
    saveSnapshot();
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
    saveSnapshot();
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

    // Convert ReactFlow state to API model
    const workflowToSave = cloneWorkflow(workflow);

    // Convert ReactFlow nodes to KillLifeWorkflowNode with updated positions
    workflowToSave.nodes = nodes.map((rfNode) => ({
      ...rfNode.data,
      x: rfNode.position.x,
      y: rfNode.position.y,
    }));

    // Convert ReactFlow edges to API edges
    workflowToSave.edges = edges.map((rfEdge) => ({
      id: rfEdge.id,
      source: rfEdge.source,
      target: rfEdge.target,
      label: typeof rfEdge.label === 'string' ? rfEdge.label : undefined,
    }));

    const result = await saveAction.execute(workflowToSave);
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
              <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">graph editor</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent font-bold text-accent md:text-5xl">
                {workflow.title}
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-[#1d1d1f]/60 md:text-[15px]">
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
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">graph</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {workflow.nodes.length.toString().padStart(2, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                  Nodes / {workflow.edges.length} edges
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">latest run</p>
                <p className="mt-3 text-sm leading-6 text-[#1d1d1f]">
                  {displayedRuns[0] ? `${displayedRuns[0].mode} / ${displayedRuns[0].status}` : "none"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
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
                  saveSnapshot();
                  setWorkflow((current) => (current ? autoLayoutDagre(current) : current));
                  setDirty(true);
                  // Fit view after layout is applied
                  setTimeout(() => {
                    reactFlowInstance.current?.fitView({ padding: 0.2, duration: 400 });
                  }, 50);
                }}
              >
                auto layout
              </Button>
              <Button variant="ghost" onClick={undo} disabled={historyPast.length === 0}>
                undo
              </Button>
              <Button variant="ghost" onClick={redo} disabled={historyFuture.length === 0}>
                redo
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
              className="overflow-hidden rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7]"
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
                onNodeDragStop={(_, node) => {
                  saveSnapshot();
                  setWorkflow((current) => {
                    if (!current) return current;
                    const next = cloneWorkflow(current);
                    const wfNode = next.nodes.find((n) => n.id === node.id);
                    if (wfNode) {
                      wfNode.x = node.position.x;
                      wfNode.y = node.position.y;
                    }
                    return next;
                  });
                  setDirty(true);
                }}
                onInit={(instance) => {
                  reactFlowInstance.current = instance;
                }}
                nodeTypes={nodeTypes}
                fitView
                className="bg-[#f5f5f7]"
              >
                <Background color="#0071e3" gap={16} size={1} />
                <Controls className="bg-[#f5f5f7] border-[rgba(0,0,0,0.08)]" />
                <MiniMap
                  className="bg-[#f5f5f7] border border-[rgba(0,0,0,0.08)]"
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
              <p className="text-sm leading-7 text-[#1d1d1f]/52">Select a node on the canvas to edit it.</p>
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

                <div className="space-y-3 rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-muted">outgoing edges</p>
                  {outgoingEdges.length === 0 ? (
                    <p className="text-sm leading-6 text-[#1d1d1f]/45">No outgoing edge yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {outgoingEdges.map((edge) => (
                        <div key={edge.id} className="flex items-center justify-between gap-3 rounded-2xl border border-[rgba(0,0,0,0.06)]/70 bg-[#f5f5f7] px-3 py-2">
                          <span className="text-xs uppercase tracking-[0.16em] text-[#1d1d1f]">
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
              <p className="text-sm leading-7 text-[#1d1d1f]/52">Run validation to inspect schema and DAG semantics.</p>
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
                    <p className="text-sm leading-6 text-[#1d1d1f]/45">Loading evidence…</p>
                  ) : evidence.data?.evidence.length ? (
                    <div className="space-y-2">
                      {evidence.data.evidence.map((entry) => (
                        <div key={entry.path} className="rounded-2xl border border-[rgba(0,0,0,0.06)]/70 bg-[#f5f5f7] px-3 py-2">
                          <p className="text-xs uppercase tracking-[0.16em] text-accent">{entry.path}</p>
                          <p className="mt-1 text-[11px] leading-5 text-[#1d1d1f]/45">
                            {entry.type} / {entry.size_bytes} bytes / {formatDate(entry.updated_at)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm leading-6 text-[#1d1d1f]/45">No evidence found for this target.</p>
                  )}
                </>
              ) : (
                <p className="text-sm leading-6 text-[#1d1d1f]/45">
                  Select an evidence node to inspect the current evidence pack surface.
                </p>
              )}

              <div className="space-y-2">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">recent runs</p>
                {displayedRuns.length === 0 ? (
                  <p className="text-sm leading-6 text-[#1d1d1f]/45">No run recorded yet.</p>
                ) : (
                  displayedRuns.slice(0, 5).map((run) => (
                    <div key={run.run_id} className="rounded-[1.35rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-accent">
                            {run.mode} / {run.status}
                          </p>
                          <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                            {formatDate(run.finished_at)} / {run.steps.length} step(s)
                          </p>
                        </div>
                        <Badge color={statusColor(run.status)}>{run.status}</Badge>
                      </div>
                      {run.steps.length > 0 ? (
                        <div className="mt-3 space-y-2">
                          {run.steps.map((step) => (
                            <div key={`${run.run_id}-${step.node_id}`} className="rounded-2xl border border-[rgba(0,0,0,0.06)]/70 bg-[#f5f5f7] px-3 py-2">
                              <div className="flex flex-wrap items-center justify-between gap-3">
                                <span className="text-[11px] uppercase tracking-[0.16em] text-[#1d1d1f]">
                                  {step.label}
                                </span>
                                <Badge color={statusColor(step.status)}>{step.status}</Badge>
                              </div>
                              <p className="mt-2 text-[11px] leading-5 text-[#1d1d1f]/45">
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
          className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#1d1d1f] transition hover:border-accent/15 hover:text-accent"
        >
          back to registry
        </Link>
      </div>
    </div>
  );
}
