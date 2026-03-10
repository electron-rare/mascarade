import { randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { copyFile, mkdir, readdir, readFile, rename, stat, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { coreClient } from "../client/core.js";

const DEFAULT_KILL_LIFE_ROOT = process.env.KILL_LIFE_ROOT || "/home/clems/Kill_LIFE";
const DEFAULT_GITHUB_REPO = process.env.KILL_LIFE_GITHUB_REPO || "electron-rare/Kill_LIFE";
const DEFAULT_GITHUB_REF = process.env.KILL_LIFE_GITHUB_REF || "main";
const DEFAULT_PIO_MODE = process.env.KILL_LIFE_PIO_MODE || "container";

const WORKFLOW_ID_RE = /^[a-z0-9][a-z0-9._-]{1,63}$/;
const TARGET_RE = /^[a-z0-9][a-z0-9._-]{1,63}$/;
const SAFE_INPUT_KEY_RE = /^[a-zA-Z0-9_.-]{1,64}$/;

const ALLOWED_NODE_TYPES = new Set([
  "note",
  "group",
  "decision",
  "manual-gate",
  "local-action",
  "github-dispatch",
]);

const ALLOWED_LOCAL_ACTIONS = new Map<
  string,
  (config: Record<string, unknown>) => { command: string[]; evidenceRefs: string[] }
>([
  [
    "compliance.validate",
    () => ({
      command: ["python3", "tools/compliance/validate.py", "--strict"],
      evidenceRefs: [],
    }),
  ],
  [
    "ci.audit",
    () => ({
      command: ["python3", "tools/ci/ci_audit.py"],
      evidenceRefs: ["docs/ci-audit-summary.json"],
    }),
  ],
  [
    "firmware.build.esp",
    () => ({
      command: ["python3", "tools/build_firmware.py", "esp"],
      evidenceRefs: [
        "docs/evidence/esp/build.result.json",
        "docs/evidence/esp/build.stdout.txt",
        "docs/evidence/esp/build.stderr.txt",
      ],
    }),
  ],
  [
    "firmware.test.linux",
    () => ({
      command: ["python3", "tools/test_firmware.py", "linux"],
      evidenceRefs: [
        "docs/evidence/linux/test.result.json",
        "docs/evidence/linux/test.stdout.txt",
        "docs/evidence/linux/test.stderr.txt",
      ],
    }),
  ],
  [
    "evidence.collect",
    (config) => {
      const target = readTarget(config);
      return {
        command: ["python3", "tools/collect_evidence.py", target],
        evidenceRefs: [`docs/evidence/${target}`],
      };
    },
  ],
  [
    "evidence.verify",
    (config) => {
      const target = readTarget(config);
      return {
        command: ["python3", "tools/verify_evidence.py", target],
        evidenceRefs: [`docs/evidence/${target}`],
      };
    },
  ],
]);

const ALLOWED_GITHUB_WORKFLOWS = new Set([
  "badges.yml",
  "evidence_pack.yml",
  "release_signing.yml",
  "repo_state.yml",
  "static.yml",
]);

const RUN_MODES = new Set(["local", "github"]);
const RUNNER_KINDS = new Set(["none", "local-action", "github-dispatch"]);

export type KillLifeWorkflowNode = {
  id: string;
  type: string;
  label: string;
  description?: string;
  x: number;
  y: number;
  runner?: {
    kind?: string;
    action?: string;
    workflow_file?: string;
    ref?: string;
    inputs?: Record<string, unknown>;
  };
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

export type KillLifeRunOptions = {
  mode: "local" | "github";
  dry_run?: boolean;
  inputs?: Record<string, unknown>;
};

export type KillLifeEvidenceEntry = {
  path: string;
  type: "file" | "directory";
  size_bytes: number;
  updated_at: string;
};

function killLifeRoot(): string {
  return path.resolve(DEFAULT_KILL_LIFE_ROOT);
}

function workflowsDir(): string {
  return path.join(killLifeRoot(), "workflows");
}

function backupsDir(): string {
  return path.join(killLifeRoot(), ".mascarade", "backups", "workflows");
}

function runsDir(): string {
  return path.join(killLifeRoot(), ".mascarade", "runs");
}

function nowIso(): string {
  return new Date().toISOString();
}

function trimExcerpt(value: string, limit = 1200): string {
  const trimmed = value.trim();
  if (trimmed.length <= limit) return trimmed;
  return `${trimmed.slice(0, limit)}…`;
}

function readTarget(config: Record<string, unknown>): string {
  const value = typeof config.target === "string" ? config.target.trim() : "";
  if (!TARGET_RE.test(value)) {
    throw new Error("Target must be a safe slug");
  }
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

export function assertSafeWorkflowId(workflowId: string): string {
  const normalized = workflowId.trim();
  if (!WORKFLOW_ID_RE.test(normalized)) {
    throw new Error(`Invalid workflow id '${workflowId}'`);
  }
  return normalized;
}

function resolveWorkflowPath(workflowId: string): string {
  const safeId = assertSafeWorkflowId(workflowId);
  const candidate = path.join(workflowsDir(), `${safeId}.json`);
  const relative = path.relative(workflowsDir(), candidate);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error("Unsafe workflow path");
  }
  return candidate;
}

async function readJson<T>(filePath: string): Promise<T> {
  return JSON.parse(await readFile(filePath, "utf-8")) as T;
}

async function writeJsonAtomic(filePath: string, payload: unknown): Promise<void> {
  await mkdir(path.dirname(filePath), { recursive: true });
  const tmpPath = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(tmpPath, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
  await rename(tmpPath, filePath);
}

function normalizeModes(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === "string");
}

function normalizeTags(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === "string");
}

export function validateWorkflowDocument(value: unknown): KillLifeValidation {
  const schema_errors: string[] = [];
  const semantic_errors: string[] = [];
  const warnings: string[] = [];

  if (!isRecord(value)) {
    return {
      valid: false,
      schema_errors: ["Workflow document must be an object"],
      semantic_errors,
      warnings,
    };
  }

  const doc = value as Record<string, unknown>;
  const requiredFields = ["id", "title", "category", "version", "status", "execution_modes", "viewport", "nodes", "edges"];
  for (const field of requiredFields) {
    if (!(field in doc)) {
      schema_errors.push(`Missing required field '${field}'`);
    }
  }

  if (typeof doc.id !== "string" || !WORKFLOW_ID_RE.test(doc.id)) {
    schema_errors.push("Field 'id' must be a safe slug");
  }
  if (typeof doc.title !== "string" || doc.title.trim().length < 3) {
    schema_errors.push("Field 'title' must be a non-empty string");
  }
  if (typeof doc.category !== "string" || doc.category.trim().length < 2) {
    schema_errors.push("Field 'category' must be a non-empty string");
  }
  if (typeof doc.version !== "number" || !Number.isInteger(doc.version) || doc.version < 1) {
    schema_errors.push("Field 'version' must be an integer >= 1");
  }
  if (typeof doc.status !== "string" || !["draft", "ready", "archived"].includes(doc.status)) {
    schema_errors.push("Field 'status' must be draft, ready, or archived");
  }

  const modes = normalizeModes(doc.execution_modes);
  if (modes.length === 0) {
    schema_errors.push("Field 'execution_modes' must contain at least one mode");
  }
  for (const mode of modes) {
    if (!RUN_MODES.has(mode)) {
      schema_errors.push(`Unsupported execution mode '${mode}'`);
    }
  }

  if (!isRecord(doc.viewport)) {
    schema_errors.push("Field 'viewport' must be an object");
  } else {
    const { width, height } = doc.viewport;
    if (typeof width !== "number" || !Number.isFinite(width) || width < 640) {
      schema_errors.push("Viewport width must be >= 640");
    }
    if (typeof height !== "number" || !Number.isFinite(height) || height < 480) {
      schema_errors.push("Viewport height must be >= 480");
    }
  }

  if (!Array.isArray(doc.nodes) || doc.nodes.length === 0) {
    schema_errors.push("Field 'nodes' must be a non-empty array");
  }
  if (!Array.isArray(doc.edges)) {
    schema_errors.push("Field 'edges' must be an array");
  }

  if (schema_errors.length > 0) {
    return {
      valid: false,
      schema_errors,
      semantic_errors,
      warnings,
    };
  }

  const nodes = doc.nodes as unknown[];
  const edges = doc.edges as unknown[];
  const nodeIds = new Set<string>();
  let executableNodeCount = 0;
  let localNodeCount = 0;
  let githubNodeCount = 0;

  for (const [index, rawNode] of nodes.entries()) {
    if (!isRecord(rawNode)) {
      semantic_errors.push(`Node #${index + 1} must be an object`);
      continue;
    }
    const node = rawNode as Record<string, unknown>;
    const nodeId = typeof node.id === "string" ? node.id : "";
    if (!WORKFLOW_ID_RE.test(nodeId)) {
      semantic_errors.push(`Node #${index + 1} has an invalid id`);
      continue;
    }
    if (nodeIds.has(nodeId)) {
      semantic_errors.push(`Duplicate node id '${nodeId}'`);
      continue;
    }
    nodeIds.add(nodeId);

    if (typeof node.label !== "string" || node.label.trim().length === 0) {
      semantic_errors.push(`Node '${nodeId}' must define a label`);
    }
    if (typeof node.type !== "string" || !ALLOWED_NODE_TYPES.has(node.type)) {
      semantic_errors.push(`Node '${nodeId}' uses unsupported type '${String(node.type)}'`);
    }
    if (typeof node.x !== "number" || !Number.isFinite(node.x)) {
      semantic_errors.push(`Node '${nodeId}' has an invalid x position`);
    }
    if (typeof node.y !== "number" || !Number.isFinite(node.y)) {
      semantic_errors.push(`Node '${nodeId}' has an invalid y position`);
    }

    const runner = isRecord(node.runner) ? node.runner : {};
    const runnerKind = typeof runner.kind === "string" ? runner.kind : "none";
    if (!RUNNER_KINDS.has(runnerKind)) {
      semantic_errors.push(`Node '${nodeId}' uses unsupported runner kind '${runnerKind}'`);
      continue;
    }

    if (runnerKind === "local-action") {
      executableNodeCount += 1;
      localNodeCount += 1;
      if (typeof runner.action !== "string" || !ALLOWED_LOCAL_ACTIONS.has(runner.action)) {
        semantic_errors.push(`Node '${nodeId}' uses unsupported local action '${String(runner.action)}'`);
      }
      if (!modes.includes("local")) {
        warnings.push(`Node '${nodeId}' is local-action but workflow execution_modes does not include 'local'`);
      }
    }

    if (runnerKind === "github-dispatch") {
      executableNodeCount += 1;
      githubNodeCount += 1;
      if (
        typeof runner.workflow_file !== "string" ||
        !ALLOWED_GITHUB_WORKFLOWS.has(runner.workflow_file)
      ) {
        semantic_errors.push(`Node '${nodeId}' uses a non-allowlisted GitHub workflow`);
      }
      if (!modes.includes("github")) {
        warnings.push(`Node '${nodeId}' is github-dispatch but workflow execution_modes does not include 'github'`);
      }
    }
  }

  const edgeIds = new Set<string>();
  const indegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();
  for (const nodeId of nodeIds) {
    indegree.set(nodeId, 0);
    adjacency.set(nodeId, []);
  }

  for (const [index, rawEdge] of edges.entries()) {
    if (!isRecord(rawEdge)) {
      semantic_errors.push(`Edge #${index + 1} must be an object`);
      continue;
    }
    const edge = rawEdge as Record<string, unknown>;
    const edgeId = typeof edge.id === "string" ? edge.id : "";
    const source = typeof edge.source === "string" ? edge.source : "";
    const target = typeof edge.target === "string" ? edge.target : "";

    if (!WORKFLOW_ID_RE.test(edgeId)) {
      semantic_errors.push(`Edge #${index + 1} has an invalid id`);
      continue;
    }
    if (edgeIds.has(edgeId)) {
      semantic_errors.push(`Duplicate edge id '${edgeId}'`);
      continue;
    }
    edgeIds.add(edgeId);

    if (!nodeIds.has(source)) {
      semantic_errors.push(`Edge '${edgeId}' source '${source}' does not exist`);
      continue;
    }
    if (!nodeIds.has(target)) {
      semantic_errors.push(`Edge '${edgeId}' target '${target}' does not exist`);
      continue;
    }
    adjacency.get(source)?.push(target);
    indegree.set(target, (indegree.get(target) || 0) + 1);
  }

  if (nodeIds.size > 0) {
    const roots = Array.from(indegree.entries())
      .filter(([, count]) => count === 0)
      .map(([nodeId]) => nodeId);
    if (roots.length === 0) {
      semantic_errors.push("Workflow must have at least one start node");
    } else if (roots.length > 1) {
      warnings.push(`Workflow has multiple start nodes: ${roots.join(", ")}`);
    }

    const queue = roots.slice();
    let visited = 0;
    const indegreeCopy = new Map(indegree);
    while (queue.length > 0) {
      const current = queue.shift();
      if (!current) continue;
      visited += 1;
      for (const next of adjacency.get(current) || []) {
        indegreeCopy.set(next, (indegreeCopy.get(next) || 0) - 1);
        if ((indegreeCopy.get(next) || 0) === 0) {
          queue.push(next);
        }
      }
    }
    if (visited !== nodeIds.size) {
      semantic_errors.push("Workflow contains a cycle; v1 only supports DAG execution");
    }
  }

  if (executableNodeCount === 0) {
    warnings.push("Workflow has no executable nodes");
  }
  if (localNodeCount === 0 && modes.includes("local")) {
    warnings.push("Workflow enables 'local' mode but has no local-action nodes");
  }
  if (githubNodeCount === 0 && modes.includes("github")) {
    warnings.push("Workflow enables 'github' mode but has no github-dispatch nodes");
  }

  return {
    valid: schema_errors.length === 0 && semantic_errors.length === 0,
    schema_errors,
    semantic_errors,
    warnings,
  };
}

export async function getWorkflow(workflowId: string): Promise<KillLifeWorkflow> {
  const filePath = resolveWorkflowPath(workflowId);
  return readJson<KillLifeWorkflow>(filePath);
}

async function latestRunFor(workflowId: string): Promise<KillLifeWorkflowSummary["latest_run"]> {
  const runs = await listWorkflowRuns(workflowId, 1);
  const first = runs[0];
  if (!first) return null;
  return {
    run_id: first.run_id,
    mode: first.mode,
    status: first.status,
    finished_at: first.finished_at,
  };
}

export async function listWorkflows(): Promise<KillLifeWorkflowSummary[]> {
  await mkdir(workflowsDir(), { recursive: true });
  const entries = await readdir(workflowsDir(), { withFileTypes: true });
  const workflowFiles = entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".json") && entry.name !== "workflow.schema.json")
    .map((entry) => entry.name)
    .sort();

  const summaries = await Promise.all(
    workflowFiles.map(async (fileName) => {
      const filePath = path.join(workflowsDir(), fileName);
      const workflow = await readJson<KillLifeWorkflow>(filePath);
      const fileStat = await stat(filePath);
      return {
        id: workflow.id,
        title: workflow.title,
        category: workflow.category,
        status: workflow.status,
        version: workflow.version,
        tags: normalizeTags(workflow.tags),
        execution_modes: normalizeModes(workflow.execution_modes),
        node_count: workflow.nodes.length,
        edge_count: workflow.edges.length,
        updated_at: fileStat.mtime.toISOString(),
        latest_run: await latestRunFor(workflow.id),
      } satisfies KillLifeWorkflowSummary;
    }),
  );

  return summaries.sort((left, right) => left.title.localeCompare(right.title));
}

export async function saveWorkflow(workflowId: string, workflow: unknown): Promise<{ workflow: KillLifeWorkflow; validation: KillLifeValidation }> {
  const safeId = assertSafeWorkflowId(workflowId);
  if (!isRecord(workflow)) {
    throw new Error("Workflow payload must be an object");
  }
  if (workflow.id !== safeId) {
    throw new Error("Workflow payload id must match the route id");
  }

  const validation = validateWorkflowDocument(workflow);
  if (!validation.valid) {
    throw new Error(`Workflow validation failed: ${validation.schema_errors.concat(validation.semantic_errors).join("; ")}`);
  }

  const filePath = resolveWorkflowPath(safeId);
  await mkdir(backupsDir(), { recursive: true });
  if (existsSync(filePath)) {
    const backupPath = path.join(backupsDir(), `${safeId}.${Date.now()}.json`);
    await copyFile(filePath, backupPath);
  }
  await writeJsonAtomic(filePath, workflow);
  return {
    workflow: workflow as KillLifeWorkflow,
    validation,
  };
}

function topologicalNodeOrder(workflow: KillLifeWorkflow): string[] {
  const indegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();
  for (const node of workflow.nodes) {
    indegree.set(node.id, 0);
    adjacency.set(node.id, []);
  }
  for (const edge of workflow.edges) {
    adjacency.get(edge.source)?.push(edge.target);
    indegree.set(edge.target, (indegree.get(edge.target) || 0) + 1);
  }

  const queue = Array.from(indegree.entries())
    .filter(([, count]) => count === 0)
    .map(([nodeId]) => nodeId);
  const order: string[] = [];
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) continue;
    order.push(current);
    for (const next of adjacency.get(current) || []) {
      indegree.set(next, (indegree.get(next) || 0) - 1);
      if ((indegree.get(next) || 0) === 0) {
        queue.push(next);
      }
    }
  }

  if (order.length !== workflow.nodes.length) {
    throw new Error("Workflow contains a cycle");
  }
  return order;
}

async function executeCommand(command: string[], cwd: string, extraEnv: NodeJS.ProcessEnv = {}): Promise<{
  returncode: number;
  stdout: string;
  stderr: string;
}> {
  return new Promise((resolve, reject) => {
    const child = spawn(command[0], command.slice(1), {
      cwd,
      env: {
        ...process.env,
        ...extraEnv,
      },
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += String(chunk);
    });
    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });
    child.on("error", reject);
    child.on("close", (code) => {
      resolve({
        returncode: code ?? 1,
        stdout,
        stderr,
      });
    });
  });
}

function sanitizeGitHubInputs(inputs: Record<string, unknown>): Record<string, string> {
  const cleaned: Record<string, string> = {};
  for (const [key, value] of Object.entries(inputs)) {
    if (!SAFE_INPUT_KEY_RE.test(key)) {
      throw new Error(`Invalid GitHub input key '${key}'`);
    }
    if (value === undefined || value === null) continue;
    cleaned[key] = String(value);
  }
  return cleaned;
}

async function runGithubDispatch(
  node: KillLifeWorkflowNode,
  runtimeInputs: Record<string, unknown>,
  runId?: string,
): Promise<Omit<KillLifeRunStep, "node_id" | "label" | "type" | "mode" | "runner_kind" | "started_at" | "finished_at" | "duration_ms">> {
  const workflowFile = node.runner?.workflow_file || "";
  if (!ALLOWED_GITHUB_WORKFLOWS.has(workflowFile)) {
    throw new Error(`Workflow '${workflowFile}' is not allowlisted`);
  }

  const payload = {
    ref: typeof node.runner?.ref === "string" && node.runner.ref.trim() ? node.runner.ref.trim() : DEFAULT_GITHUB_REF,
    inputs: sanitizeGitHubInputs({
      ...(isRecord(node.runner?.inputs) ? node.runner?.inputs : {}),
      ...runtimeInputs,
    }),
  };

  const dispatch = await coreClient.githubDispatchDispatch({
    workflow_file: workflowFile,
    ref: payload.ref,
    inputs: payload.inputs,
    run_id: runId,
  });

  return {
    status: "success",
    workflow_file: workflowFile,
    ref: payload.ref,
    evidence_refs: [],
    stdout_excerpt: `workflow_dispatch accepted for ${workflowFile} via MCP${dispatch.auth_mode ? ` (${dispatch.auth_mode})` : ""}`,
    stderr_excerpt: "",
    message: "GitHub workflow dispatch accepted",
  };
}

async function runLocalAction(node: KillLifeWorkflowNode): Promise<Omit<KillLifeRunStep, "node_id" | "label" | "type" | "mode" | "runner_kind" | "started_at" | "finished_at" | "duration_ms">> {
  const action = node.runner?.action || "";
  const factory = ALLOWED_LOCAL_ACTIONS.get(action);
  if (!factory) {
    throw new Error(`Unsupported local action '${action}'`);
  }
  const prepared = factory(node.config || {});
  const result = await executeCommand(prepared.command, killLifeRoot(), {
    KILL_LIFE_PIO_MODE: DEFAULT_PIO_MODE,
  });

  return {
    status: result.returncode === 0 ? "success" : "failed",
    command: prepared.command,
    returncode: result.returncode,
    stdout_excerpt: trimExcerpt(result.stdout),
    stderr_excerpt: trimExcerpt(result.stderr),
    evidence_refs: prepared.evidenceRefs,
    message: result.returncode === 0 ? "Local action completed" : "Local action failed",
  };
}

async function persistRunRecord(record: KillLifeRunRecord): Promise<void> {
  const directory = path.join(runsDir(), record.workflow_id);
  await mkdir(directory, { recursive: true });
  await writeJsonAtomic(path.join(directory, `${record.run_id}.json`), record);
}

export async function listWorkflowRuns(workflowId: string, limit = 10): Promise<KillLifeRunRecord[]> {
  const safeId = assertSafeWorkflowId(workflowId);
  const directory = path.join(runsDir(), safeId);
  if (!existsSync(directory)) {
    return [];
  }

  const entries = await readdir(directory, { withFileTypes: true });
  const files = entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
    .map((entry) => path.join(directory, entry.name));

  const records = await Promise.all(
    files.map(async (filePath) => {
      const record = await readJson<KillLifeRunRecord>(filePath);
      const fileStat = await stat(filePath);
      return {
        record,
        updatedAt: fileStat.mtimeMs,
      };
    }),
  );

  return records
    .sort((left, right) => right.updatedAt - left.updatedAt)
    .slice(0, limit)
    .map((entry) => entry.record);
}

export async function runWorkflow(workflowId: string, options: KillLifeRunOptions): Promise<KillLifeRunRecord> {
  const workflow = await getWorkflow(workflowId);
  const validation = validateWorkflowDocument(workflow);
  if (!validation.valid) {
    throw new Error(`Workflow '${workflowId}' is invalid and cannot run`);
  }

  const mode = options.mode;
  if (!RUN_MODES.has(mode)) {
    throw new Error(`Unsupported run mode '${mode}'`);
  }
  if (!workflow.execution_modes.includes(mode)) {
    throw new Error(`Workflow '${workflowId}' does not support run mode '${mode}'`);
  }

  const dryRun = options.dry_run === true;
  const runtimeInputs = isRecord(options.inputs) ? options.inputs : {};
  const nodeOrder = topologicalNodeOrder(workflow);
  const nodeMap = new Map(workflow.nodes.map((node) => [node.id, node]));
  const runId = randomUUID();
  const startedAt = nowIso();
  const steps: KillLifeRunStep[] = [];
  let overallStatus: KillLifeRunRecord["status"] = "no-op";

  for (const nodeId of nodeOrder) {
    const node = nodeMap.get(nodeId);
    if (!node) continue;

    const runnerKind = node.runner?.kind || "none";
    const shouldRun =
      (mode === "local" && runnerKind === "local-action") ||
      (mode === "github" && runnerKind === "github-dispatch");

    if (!shouldRun) {
      continue;
    }

    const stepStarted = Date.now();
    const baseStep = {
      node_id: node.id,
      label: node.label,
      type: node.type,
      mode,
      runner_kind: runnerKind,
      started_at: new Date(stepStarted).toISOString(),
    } as const;

    if (dryRun) {
      const preview =
        mode === "local"
          ? ALLOWED_LOCAL_ACTIONS.get(node.runner?.action || "")?.(node.config || {})
          : undefined;
      const previewInputs = isRecord(node.runner?.inputs) ? sanitizeGitHubInputs(node.runner.inputs) : {};
      steps.push({
        ...baseStep,
        status: "dry-run",
        command: preview?.command,
        workflow_file: node.runner?.workflow_file,
        ref: node.runner?.ref,
        finished_at: nowIso(),
        duration_ms: 0,
        evidence_refs: preview?.evidenceRefs || [],
        stdout_excerpt:
          mode === "local"
            ? `Would run: ${(preview?.command || []).join(" ")}`
            : `Would dispatch ${node.runner?.workflow_file || "unknown workflow"} with inputs ${JSON.stringify({
                ...previewInputs,
                ...sanitizeGitHubInputs(runtimeInputs),
              })}`,
        stderr_excerpt: "",
        message: "Dry run only",
      });
      overallStatus = "success";
      continue;
    }

    try {
      const result =
        mode === "local"
          ? await runLocalAction(node)
          : await runGithubDispatch(node, runtimeInputs, runId);
      const finishedAt = nowIso();
      const durationMs = Date.now() - stepStarted;
      steps.push({
        ...baseStep,
        ...result,
        finished_at: finishedAt,
        duration_ms: durationMs,
      });
      overallStatus = result.status === "success" ? "success" : "failed";
      if (result.status === "failed") {
        break;
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown execution error";
      steps.push({
        ...baseStep,
        status: "failed",
        finished_at: nowIso(),
        duration_ms: Date.now() - stepStarted,
        evidence_refs: [],
        stdout_excerpt: "",
        stderr_excerpt: trimExcerpt(message),
        message,
      });
      overallStatus = "failed";
      break;
    }
  }

  const record: KillLifeRunRecord = {
    run_id: runId,
    workflow_id: workflow.id,
    workflow_title: workflow.title,
    mode,
    dry_run: dryRun,
    status: overallStatus,
    started_at: startedAt,
    finished_at: nowIso(),
    steps,
  };
  await persistRunRecord(record);
  return record;
}

export async function listEvidence(target: string): Promise<KillLifeEvidenceEntry[]> {
  if (!TARGET_RE.test(target)) {
    throw new Error("Invalid evidence target");
  }
  const directory = path.join(killLifeRoot(), "docs", "evidence", target);
  if (!existsSync(directory)) {
    return [];
  }
  const entries = await readdir(directory, { withFileTypes: true });
  const results = await Promise.all(
    entries.map(async (entry) => {
      const absolutePath = path.join(directory, entry.name);
      const fileStat = await stat(absolutePath);
      return {
        path: path.relative(killLifeRoot(), absolutePath).replaceAll(path.sep, "/"),
        type: entry.isDirectory() ? "directory" : "file",
        size_bytes: fileStat.size,
        updated_at: fileStat.mtime.toISOString(),
      } satisfies KillLifeEvidenceEntry;
    }),
  );
  return results.sort((left, right) => left.path.localeCompare(right.path));
}

export async function deleteRunRecord(workflowId: string, runId: string): Promise<void> {
  const safeWorkflowId = assertSafeWorkflowId(workflowId);
  const safeRunId = runId.replace(/[^a-zA-Z0-9._-]/g, "");
  if (!safeRunId) {
    throw new Error("Invalid run id");
  }
  const filePath = path.join(runsDir(), safeWorkflowId, `${safeRunId}.json`);
  if (existsSync(filePath)) {
    await unlink(filePath);
  }
}
