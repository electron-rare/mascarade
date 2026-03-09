import { get, post, put } from "./client";

export type KillLifeNodeRunner = {
  kind?: string;
  action?: string;
  workflow_file?: string;
  ref?: string;
  inputs?: Record<string, unknown>;
};

export type KillLifeWorkflowNode = {
  id: string;
  type: string;
  label: string;
  description?: string;
  x: number;
  y: number;
  runner?: KillLifeNodeRunner;
  config?: Record<string, unknown>;
};

export type KillLifeWorkflowEdge = {
  id: string;
  source: string;
  target: string;
  label?: string;
};

export type KillLifeWorkflow = {
  id: string;
  title: string;
  category: string;
  version: number;
  status: string;
  description?: string;
  tags?: string[];
  execution_modes: string[];
  viewport: {
    width: number;
    height: number;
  };
  nodes: KillLifeWorkflowNode[];
  edges: KillLifeWorkflowEdge[];
};

export type KillLifeValidation = {
  valid: boolean;
  schema_errors: string[];
  semantic_errors: string[];
  warnings: string[];
};

export type KillLifeRunStep = {
  node_id: string;
  label: string;
  type: string;
  status: "success" | "failed" | "skipped" | "dry-run";
  mode: "local" | "github";
  runner_kind: string;
  command?: string[];
  workflow_file?: string;
  ref?: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  returncode?: number;
  stdout_excerpt?: string;
  stderr_excerpt?: string;
  evidence_refs: string[];
  message?: string;
};

export type KillLifeRunRecord = {
  run_id: string;
  workflow_id: string;
  workflow_title: string;
  mode: "local" | "github";
  dry_run: boolean;
  status: "success" | "failed" | "no-op";
  started_at: string;
  finished_at: string;
  steps: KillLifeRunStep[];
};

export type KillLifeWorkflowSummary = {
  id: string;
  title: string;
  category: string;
  status: string;
  version: number;
  tags: string[];
  execution_modes: string[];
  node_count: number;
  edge_count: number;
  updated_at: string;
  latest_run: Pick<KillLifeRunRecord, "run_id" | "mode" | "status" | "finished_at"> | null;
};

export type KillLifeEvidenceEntry = {
  path: string;
  type: "file" | "directory";
  size_bytes: number;
  updated_at: string;
};

export const killLifeApi = {
  list: () =>
    get<{
      root: string;
      workflows: KillLifeWorkflowSummary[];
    }>("/api/killlife/workflows"),

  get: (workflowId: string) =>
    get<{
      workflow: KillLifeWorkflow;
      validation: KillLifeValidation;
      runs: KillLifeRunRecord[];
    }>(`/api/killlife/workflows/${encodeURIComponent(workflowId)}`),

  save: (workflowId: string, workflow: KillLifeWorkflow) =>
    put<{
      workflow: KillLifeWorkflow;
      validation: KillLifeValidation;
    }>(`/api/killlife/workflows/${encodeURIComponent(workflowId)}`, workflow),

  validate: (workflowId: string, workflow: KillLifeWorkflow) =>
    post<KillLifeValidation>(`/api/killlife/workflows/${encodeURIComponent(workflowId)}/validate`, workflow),

  run: (
    workflowId: string,
    body: {
      mode: "local" | "github";
      dry_run?: boolean;
      inputs?: Record<string, unknown>;
    },
  ) =>
    post<KillLifeRunRecord>(
      `/api/killlife/workflows/${encodeURIComponent(workflowId)}/run`,
      body,
    ),

  runs: (workflowId: string) =>
    get<{ runs: KillLifeRunRecord[] }>(
      `/api/killlife/workflows/${encodeURIComponent(workflowId)}/runs`,
    ),

  evidence: (target: string) =>
    get<{ evidence: KillLifeEvidenceEntry[] }>(`/api/killlife/evidence/${encodeURIComponent(target)}`),
};
