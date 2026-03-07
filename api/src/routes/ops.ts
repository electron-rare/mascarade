import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { Hono } from "hono";
import {
  coreClient,
  getCoreAuthHeaders,
  type AgentTraceEvent,
} from "../client/core.js";
import { handleCoreError } from "../middleware/error.js";

type ProbeResult = {
  name: string;
  url: string;
  ok: boolean;
  status: number;
  latency_ms: number;
  error?: string;
};

type TimedJsonResult = {
  ok: boolean;
  status: number;
  latencyMs: number;
  json?: any;
  error?: string;
};

type OpsLogEntry = {
  id: string;
  ts: string;
  source: "service" | "machine" | "agent-trace" | "docker-event";
  service?: string;
  severity: "debug" | "info" | "warning" | "error" | "critical";
  message: string;
  run_id?: string;
  agent_name?: string | null;
  from_agent?: string | null;
  to_agent?: string | null;
  event_type?: string;
  labels?: Record<string, string>;
};

type MonitorSnapshot = {
  timestamp: string;
  gateway: {
    api: { ok: boolean; status: number };
    core: boolean;
  };
  ai: {
    ollama: {
      ok: boolean;
      status: number;
      latency_ms: number;
      models: number;
      model_names: string[];
      error?: string;
    };
    apple_llm: null | {
      ok: boolean;
      status: number;
      latency_ms: number;
      backend: string | null;
      model_id: string | null;
      runtime_ready: boolean | null;
      error?: string | null;
    };
    qdrant: {
      ok: boolean;
      status: number;
      latency_ms: number;
      collections: number;
      error?: string;
    };
  };
  services: ProbeResult[];
  core_metrics: {
    ok: boolean;
    status: number;
    data: Record<string, unknown> | null;
    error?: string;
  };
};

type McpProbePayload = {
  status?: string;
  requested_runtime?: string;
  runtime_mode?: string;
  quick?: boolean;
  protocol_version?: string | null;
  server_name?: string | null;
  tool_count?: number;
  resource_count?: number;
  prompt_count?: number;
  checks?: string[];
  secret_configured?: boolean;
  token_configured?: boolean;
  live_requested?: boolean;
  live_validation?: string | null;
  error?: string;
};

type McpRuntimeStatus = {
  ok: boolean;
  status: "ready" | "degraded" | "failed";
  requested_runtime: string;
  runtime_mode: string | null;
  protocol_version: string | null;
  server_name: string | null;
  tool_count: number;
  resource_count: number;
  prompt_count: number;
  latency_ms: number;
  checks: string[];
  secret_configured?: boolean;
  token_configured?: boolean;
  live_requested?: boolean;
  live_validation?: string | null;
  error?: string;
};

type McpSuiteStatus = McpRuntimeStatus & {
  aggregate_status: "ready" | "degraded" | "failed";
  primary_server: string;
  primary: McpRuntimeStatus;
  server_count: number;
  servers_ok: number;
  degraded_servers: string[];
  servers: Record<string, McpRuntimeStatus>;
};

type McpProbeConfig = {
  key: string;
  command: string[];
  cwd: string;
  timeout_ms: number;
  primary?: boolean;
};

async function timedJson(
  url: string,
  timeoutMs: number = 1800,
  headers?: Record<string, string>,
): Promise<TimedJsonResult> {
  const started = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { headers, signal: controller.signal });
    const latencyMs = Date.now() - started;
    const json = await res.json().catch(() => undefined);
    return { ok: res.ok, status: res.status, latencyMs, json };
  } catch (error) {
    const latencyMs = Date.now() - started;
    return {
      ok: false,
      status: 0,
      latencyMs,
      error: error instanceof Error ? error.message : "network error",
    };
  } finally {
    clearTimeout(timer);
  }
}

async function timedProbe(
  name: string,
  url: string,
  timeoutMs: number = 1500,
): Promise<ProbeResult> {
  const started = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    return {
      name,
      url,
      ok: res.ok,
      status: res.status,
      latency_ms: Date.now() - started,
    };
  } catch (error) {
    return {
      name,
      url,
      ok: false,
      status: 0,
      latency_ms: Date.now() - started,
      error: error instanceof Error ? error.message : "network error",
    };
  } finally {
    clearTimeout(timer);
  }
}

const OLLAMA_BASE_URL = (process.env.OLLAMA_BASE_URL || "http://ollama:11434").replace(/\/+$/, "");
const APPLE_LLM_ENABLED = (process.env.APPLE_LLM_ENABLED || "").toLowerCase() === "true";
const APPLE_LLM_BASE_URL = (process.env.APPLE_LLM_BASE_URL || "").replace(/\/+$/, "");
const OPS_AGENT_URL = (process.env.OPS_AGENT_URL || "http://ops-agent:9200").replace(/\/+$/, "");
const LOKI_URL = (process.env.LOKI_URL || "http://loki:3100").replace(/\/+$/, "");
const CORE_URL = (process.env.CORE_URL || "http://core:8100").replace(/\/+$/, "");
const KILL_LIFE_ROOT = path.resolve(process.env.KILL_LIFE_ROOT || "/home/clems/Kill_LIFE");
const KILL_LIFE_MCP_SMOKE = path.join(KILL_LIFE_ROOT, "tools", "hw", "mcp_smoke.py");
const KILL_LIFE_VALIDATE_SPECS_MCP_SMOKE = path.join(
  KILL_LIFE_ROOT,
  "tools",
  "validate_specs_mcp_smoke.py",
);
const KILL_LIFE_NOTION_MCP_SMOKE = path.join(
  KILL_LIFE_ROOT,
  "tools",
  "notion_mcp_smoke.py",
);
const KILL_LIFE_GITHUB_DISPATCH_MCP_SMOKE = path.join(
  KILL_LIFE_ROOT,
  "tools",
  "github_dispatch_mcp_smoke.py",
);
const OPS_MCP_PROBE_CACHE_TTL_MS = Math.max(
  1000,
  Number(process.env.OPS_MCP_PROBE_CACHE_TTL_MS || "15000") || 15000,
);
const MCP_PROBE_CONFIGS: McpProbeConfig[] = [
  {
    key: "kicad",
    command: ["python3", KILL_LIFE_MCP_SMOKE, "--json", "--quick", "--timeout", "8.0"],
    cwd: KILL_LIFE_ROOT,
    timeout_ms: 8000,
    primary: true,
  },
  {
    key: "validate-specs",
    command: ["python3", KILL_LIFE_VALIDATE_SPECS_MCP_SMOKE, "--json", "--quick", "--timeout", "8.0"],
    cwd: KILL_LIFE_ROOT,
    timeout_ms: 8000,
  },
  {
    key: "notion",
    command: ["python3", KILL_LIFE_NOTION_MCP_SMOKE, "--json", "--quick", "--timeout", "8.0"],
    cwd: KILL_LIFE_ROOT,
    timeout_ms: 8000,
  },
  {
    key: "github-dispatch",
    command: [
      "python3",
      KILL_LIFE_GITHUB_DISPATCH_MCP_SMOKE,
      "--json",
      "--quick",
      "--timeout",
      "8.0",
    ],
    cwd: KILL_LIFE_ROOT,
    timeout_ms: 8000,
  },
];

let cachedMcpProbe:
  | {
      expiresAt: number;
      value: McpSuiteStatus;
    }
  | null = null;
let inflightMcpProbe: Promise<McpSuiteStatus> | null = null;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseJsonRecord(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value);
    return isRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

type DecodedLokiLine = {
  line: string;
  structured: Record<string, unknown> | null;
  envelopeTs?: string;
};

export function decodeLokiLine(rawLine: string): DecodedLokiLine {
  let currentLine = rawLine.trim();
  let envelopeTs: string | undefined;

  for (let depth = 0; depth < 3; depth += 1) {
    const parsed = parseJsonRecord(currentLine);
    if (!parsed) {
      return { line: currentLine, structured: null, envelopeTs };
    }
    if (typeof parsed.log === "string") {
      currentLine = parsed.log.trim();
      if (!envelopeTs && typeof parsed.time === "string") {
        envelopeTs = parsed.time;
      }
      continue;
    }
    return { line: currentLine, structured: parsed, envelopeTs };
  }

  return { line: currentLine, structured: null, envelopeTs };
}

function coerceSource(value: unknown, fallback: OpsLogEntry["source"]): OpsLogEntry["source"] {
  return value === "agent-trace" ||
    value === "machine" ||
    value === "service" ||
    value === "docker-event"
    ? value
    : fallback;
}

function fallbackSourceFromLabels(labels: Record<string, string>): OpsLogEntry["source"] {
  return labels.job === "systemd-journal" ? "machine" : "service";
}

function coerceOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function extractServiceFromLabels(labels: Record<string, string>): string | undefined {
  const direct =
    labels.service ||
    labels.compose_service ||
    labels.container ||
    labels.container_name ||
    labels.unit;
  if (direct) {
    return direct;
  }

  const filename = labels.filename || labels.__path__ || "";
  const containerMatch = /\/containers\/([a-f0-9]{12,64})\//i.exec(filename);
  if (containerMatch) {
    return containerMatch[1].slice(0, 12);
  }
  return undefined;
}

function normalizedIsoTimestamp(rawTimestampNs: string, envelopeTs?: string): string {
  if (envelopeTs) {
    const parsed = new Date(envelopeTs);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toISOString();
    }
  }
  return new Date(Number(rawTimestampNs) / 1_000_000).toISOString();
}

export function lokiValueToOpsLogEntry(args: {
  rawTimestampNs: string;
  rawLine: string;
  labels?: Record<string, string>;
}): OpsLogEntry | null {
  const labels = args.labels ?? {};
  const decoded = decodeLokiLine(args.rawLine);
  const ts = normalizedIsoTimestamp(args.rawTimestampNs, decoded.envelopeTs);
  const fallbackSource = fallbackSourceFromLabels(labels);

  if (decoded.structured) {
    const source = coerceSource(decoded.structured.source, fallbackSource);
    const message = coerceOptionalString(decoded.structured.message) || decoded.line;
    const structuredLabels = {
      ...labels,
      ...(coerceOptionalString(decoded.structured.provider)
        ? { provider: coerceOptionalString(decoded.structured.provider)! }
        : {}),
      ...(coerceOptionalString(decoded.structured.model)
        ? { model: coerceOptionalString(decoded.structured.model)! }
        : {}),
      ...(coerceOptionalString(decoded.structured.routing_role)
        ? { routing_role: coerceOptionalString(decoded.structured.routing_role)! }
        : {}),
      ...(coerceOptionalString(decoded.structured.routing_provider)
        ? { routing_provider: coerceOptionalString(decoded.structured.routing_provider)! }
        : {}),
      ...(coerceOptionalString(decoded.structured.routing_model)
        ? { routing_model: coerceOptionalString(decoded.structured.routing_model)! }
        : {}),
    };
    return {
      id:
        coerceOptionalString(decoded.structured.id) ||
        `${source}:${ts}:${coerceOptionalString(decoded.structured.run_id) || "structured"}`,
      ts,
      source,
      service: coerceOptionalString(decoded.structured.service) || extractServiceFromLabels(labels),
      severity:
        coerceSeverity(coerceOptionalString(decoded.structured.severity)) ||
        inferSeverityFromMessage(message),
      message,
      run_id: coerceOptionalString(decoded.structured.run_id),
      agent_name: coerceOptionalString(decoded.structured.agent_name),
      from_agent: coerceOptionalString(decoded.structured.from_agent),
      to_agent: coerceOptionalString(decoded.structured.to_agent),
      event_type: coerceOptionalString(decoded.structured.event_type),
      labels: structuredLabels,
    };
  }

  if (!decoded.line) {
    return null;
  }

  return {
    id: `${fallbackSource}:${ts}:plain`,
    ts,
    source: fallbackSource,
    service: extractServiceFromLabels(labels),
    severity: inferSeverityFromMessage(decoded.line),
    message: decoded.line,
    labels,
  };
}

function severityRank(severity: OpsLogEntry["severity"]): number {
  switch (severity) {
    case "debug":
      return 10;
    case "info":
      return 20;
    case "warning":
      return 30;
    case "error":
      return 40;
    case "critical":
      return 50;
    default:
      return 20;
  }
}

function labelsMatchRouting(
  entry: OpsLogEntry,
  filters: {
    routing_role?: string;
    routing_provider?: string;
    routing_model?: string;
  },
): boolean {
  const role = filters.routing_role?.trim().toLowerCase();
  const provider = filters.routing_provider?.trim().toLowerCase();
  const model = filters.routing_model?.trim().toLowerCase();
  const labels = entry.labels || {};

  if (role && (labels.routing_role || "").trim().toLowerCase() !== role) {
    return false;
  }
  if (provider && (labels.routing_provider || "").trim().toLowerCase() !== provider) {
    return false;
  }
  if (model && (labels.routing_model || "").trim().toLowerCase() !== model) {
    return false;
  }
  return true;
}

function coerceSeverity(value: string | undefined): OpsLogEntry["severity"] | null {
  if (!value) return null;
  const normalized = value.trim().toLowerCase();
  if (
    normalized === "debug" ||
    normalized === "info" ||
    normalized === "warning" ||
    normalized === "error" ||
    normalized === "critical"
  ) {
    return normalized;
  }
  return null;
}

function traceToLogEntry(event: AgentTraceEvent): OpsLogEntry {
  return {
    id: event.id,
    ts: event.ts,
    source: "agent-trace",
    severity: event.severity,
    message: event.message,
    run_id: event.run_id,
    agent_name: event.agent_name,
    from_agent: event.from_agent,
    to_agent: event.to_agent,
    event_type: event.event_type,
    labels: {
      mode: event.mode,
      provider: event.provider ?? "",
      model: event.model ?? "",
      routing_role: event.routing_role ?? "",
      routing_provider: event.routing_provider ?? "",
      routing_model: event.routing_model ?? "",
    },
  };
}

function probeToLogEntry(probe: ProbeResult, timestamp: string): OpsLogEntry | null {
  if (probe.ok) {
    return null;
  }

  const severity: OpsLogEntry["severity"] =
    probe.status >= 500 || probe.status === 0 ? "error" : "warning";

  return {
    id: `${probe.name}:${timestamp}`,
    ts: timestamp,
    source: "service",
    service: probe.name,
    severity,
    message: probe.error
      ? `${probe.name} probe failed: ${probe.error}`
      : `${probe.name} returned HTTP ${probe.status}`,
    labels: {
      url: probe.url,
      status: String(probe.status),
      latency_ms: String(probe.latency_ms),
    },
  };
}

function sortLogs(entries: OpsLogEntry[]): OpsLogEntry[] {
  return [...entries].sort((left, right) => {
    const tsDiff = new Date(right.ts).getTime() - new Date(left.ts).getTime();
    if (tsDiff !== 0) return tsDiff;
    return severityRank(right.severity) - severityRank(left.severity);
  });
}

async function opsAgentJson(
  path: string,
  timeoutMs: number = 2200,
): Promise<TimedJsonResult> {
  return timedJson(`${OPS_AGENT_URL}${path}`, timeoutMs);
}

async function proxySseResponse(
  url: string,
  headers?: Record<string, string>,
  signal?: AbortSignal,
): Promise<Response> {
  const upstream = await fetch(url, {
    headers: {
      Accept: "text/event-stream",
      ...(headers || {}),
    },
    signal,
  });

  if (!upstream.ok || !upstream.body) {
    const body = await upstream.text().catch(() => "");
    throw new Error(body || `Upstream SSE failed (${upstream.status})`);
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}

async function lokiReady(timeoutMs: number = 1600): Promise<boolean> {
  const result = await timedJson(`${LOKI_URL}/ready`, timeoutMs);
  return result.ok;
}

function makeDefaultMcpStatus(overrides: Partial<McpRuntimeStatus> = {}): McpRuntimeStatus {
  return {
    ok: false,
    status: "failed",
    requested_runtime: "local",
    runtime_mode: null,
    protocol_version: null,
    server_name: null,
    tool_count: 0,
    resource_count: 0,
    prompt_count: 0,
    latency_ms: 0,
    checks: [],
    ...overrides,
  };
}

async function runMcpProbe(config: McpProbeConfig): Promise<McpRuntimeStatus> {
  const started = Date.now();
  if (!existsSync(config.cwd)) {
    return makeDefaultMcpStatus({
      status: "degraded",
      latency_ms: Date.now() - started,
      server_name: config.key,
      error: `Probe workspace unavailable in API runtime: ${config.cwd}`,
    });
  }

  const scriptCandidate = config.command[1];
  if (scriptCandidate && (scriptCandidate.endsWith(".py") || scriptCandidate.endsWith(".sh")) && !existsSync(scriptCandidate)) {
    return makeDefaultMcpStatus({
      status: "degraded",
      latency_ms: Date.now() - started,
      server_name: config.key,
      error: `Probe script unavailable in API runtime: ${scriptCandidate}`,
    });
  }

  return await new Promise((resolve) => {
    const child = spawn(config.command[0], config.command.slice(1), {
      cwd: config.cwd,
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let settled = false;

    const finish = (payload: Partial<McpRuntimeStatus>) => {
      if (settled) return;
      settled = true;
      resolve(
        makeDefaultMcpStatus({
          latency_ms: Date.now() - started,
          ...payload,
        }),
      );
    };

    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      finish({ error: `Timed out after ${(config.timeout_ms / 1000).toFixed(1)}s waiting for MCP probe` });
    }, config.timeout_ms);

    child.stdout.on("data", (chunk) => {
      stdout += String(chunk);
    });
    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      const unavailable = /ENOENT/i.test(error.message);
      finish({
        status: unavailable ? "degraded" : "failed",
        server_name: config.key,
        error: unavailable
          ? `Probe dependency unavailable in API runtime: ${error.message}`
          : error.message,
      });
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      const line = stdout
        .split(/\r?\n/)
        .map((entry) => entry.trim())
        .filter(Boolean)
        .at(-1);

      let json: McpProbePayload | null = null;
      if (line) {
        try {
          json = JSON.parse(line) as McpProbePayload;
        } catch {
          json = null;
        }
      }

      const normalizedStatus =
        json?.status === "ready"
          ? "ready"
          : json?.status === "degraded"
            ? "degraded"
            : code === 0
              ? "degraded"
              : "failed";

      finish({
        ok: normalizedStatus === "ready",
        status: normalizedStatus,
        requested_runtime: json?.requested_runtime || "local",
        runtime_mode: json?.runtime_mode || null,
        protocol_version: json?.protocol_version || null,
        server_name: json?.server_name || config.key,
        tool_count: json?.tool_count || 0,
        resource_count: json?.resource_count || 0,
        prompt_count: json?.prompt_count || 0,
        checks: Array.isArray(json?.checks) ? json.checks : [],
        secret_configured: json?.secret_configured,
        token_configured: json?.token_configured,
        live_requested: json?.live_requested,
        live_validation: json?.live_validation,
        error:
          json?.error ||
          stderr.trim() ||
          (code === 0 ? undefined : `Probe exited with code ${code}`),
      });
    });
  });
}

function aggregateMcpStatus(servers: Record<string, McpRuntimeStatus>): McpSuiteStatus {
  const entries = Object.entries(servers);
  const primaryEntry =
    entries.find(([key]) => key === "kicad") ||
    entries.find(([key]) => MCP_PROBE_CONFIGS.find((config) => config.key === key)?.primary) ||
    entries[0];
  const [primaryServer, primary] = primaryEntry || ["unknown", makeDefaultMcpStatus()];
  const aggregateStatus = entries.some(([, status]) => status.status === "failed")
    ? "failed"
    : entries.some(([, status]) => status.status === "degraded")
      ? "degraded"
      : "ready";

  return {
    ...primary,
    ok: aggregateStatus === "ready",
    status: aggregateStatus,
    aggregate_status: aggregateStatus,
    primary_server: primaryServer,
    primary,
    server_count: entries.length,
    servers_ok: entries.filter(([, status]) => status.status === "ready").length,
    degraded_servers: entries
      .filter(([, status]) => status.status !== "ready")
      .map(([key]) => key),
    servers,
  };
}

async function probeMcpRuntime(_timeoutMs: number = 8000): Promise<McpSuiteStatus> {
  const now = Date.now();
  if (cachedMcpProbe && cachedMcpProbe.expiresAt > now) {
    return cachedMcpProbe.value;
  }
  if (inflightMcpProbe) {
    return await inflightMcpProbe;
  }

  inflightMcpProbe = (async () => {
    const statuses = await Promise.all(
      MCP_PROBE_CONFIGS.map(async (config) => [config.key, await runMcpProbe(config)] as const),
    );
    const value = aggregateMcpStatus(Object.fromEntries(statuses));
    cachedMcpProbe = {
      value,
      expiresAt: Date.now() + OPS_MCP_PROBE_CACHE_TTL_MS,
    };
    return value;
  })();

  try {
    return await inflightMcpProbe;
  } finally {
    inflightMcpProbe = null;
  }
}

async function queryLoki(params: {
  source?: string;
  limit: number;
  query?: string;
  run_id?: string;
  agent_name?: string;
  event_type?: string;
  service?: string;
  severity?: OpsLogEntry["severity"] | null;
  since?: string;
}): Promise<OpsLogEntry[]> {
  const limit = Math.max(1, Math.min(params.limit, 400));
  const selector =
    params.source === "agent-trace"
      ? `{job="docker"}`
      : params.source === "machine"
        ? `{job="systemd-journal"}`
        : params.source === "service"
          ? `{job="docker"}`
          : `{job=~"docker|systemd-journal"}`;

  const filters: string[] = [];
  if (params.query?.trim()) {
    filters.push(` |= ${JSON.stringify(params.query.trim())}`);
  }
  if (params.source === "agent-trace" && params.run_id?.trim()) {
    filters.push(` |= ${JSON.stringify(params.run_id.trim())}`);
  }
  if (params.source === "agent-trace" && params.agent_name?.trim()) {
    filters.push(` |= ${JSON.stringify(params.agent_name.trim())}`);
  }
  if (params.source === "agent-trace" && params.event_type?.trim()) {
    filters.push(` |= ${JSON.stringify(params.event_type.trim())}`);
  }
  const query = `${selector}${filters.join("")}`;
  const endNs = String(Date.now() * 1_000_000);
  const startNs = String((Date.now() - parseSinceWindow(params.since)) * 1_000_000);
  const search = new URLSearchParams({
    query,
    limit: String(limit),
    direction: "BACKWARD",
    start: startNs,
    end: endNs,
  });

  const response = await timedJson(`${LOKI_URL}/loki/api/v1/query_range?${search.toString()}`, 3500);
  if (!response.ok) {
    throw new Error(response.error || `Loki query failed (${response.status})`);
  }

  const result = response.json?.data?.result;
  if (!Array.isArray(result)) {
    return [];
  }

  const entries: OpsLogEntry[] = [];
  for (const stream of result) {
    const labels = stream?.stream ?? {};
    const values = Array.isArray(stream?.values) ? stream.values : [];
    for (const value of values) {
      if (!Array.isArray(value) || value.length < 2) continue;
      const entry = lokiValueToOpsLogEntry({
        rawTimestampNs: String(value[0] || ""),
        rawLine: String(value[1] || ""),
        labels,
      });
      if (!entry) {
        continue;
      }
      if (params.source && params.source !== "all" && entry.source !== params.source) {
        continue;
      }
      if (params.service?.trim() && entry.service !== params.service.trim()) {
        continue;
      }
      entries.push(entry);
    }
  }

  return sortLogs(entries)
    .filter((entry) => !params.severity || severityRank(entry.severity) >= severityRank(params.severity))
    .slice(0, limit);
}

function inferSeverityFromMessage(message: string): OpsLogEntry["severity"] {
  if (/\b(critical|fatal|panic)\b/i.test(message)) return "critical";
  if (/\b(error|exception|traceback|failed)\b/i.test(message)) return "error";
  if (/\b(warn|warning)\b/i.test(message)) return "warning";
  if (/\b(debug|trace)\b/i.test(message)) return "debug";
  return "info";
}

function parseSinceWindow(value: string | undefined): number {
  if (!value) return 60 * 60 * 1000;
  const match = /^(\d+)([smhd])$/i.exec(value.trim());
  if (!match) return 60 * 60 * 1000;

  const amount = Number.parseInt(match[1], 10);
  if (!Number.isFinite(amount) || amount <= 0) return 60 * 60 * 1000;

  const unit = match[2].toLowerCase();
  if (unit === "s") return amount * 1000;
  if (unit === "m") return amount * 60 * 1000;
  if (unit === "h") return amount * 60 * 60 * 1000;
  if (unit === "d") return amount * 24 * 60 * 60 * 1000;
  return 60 * 60 * 1000;
}

async function collectMonitorSnapshot(): Promise<MonitorSnapshot> {
  const probes = await Promise.all([
    timedProbe("core", "http://core:8100/health"),
    timedProbe("openwebui", "http://open-webui:8080/"),
    timedProbe("grafana", "http://grafana:3000/api/health"),
    timedProbe("n8n", "http://n8n:5678/"),
    timedProbe("langfuse", "http://langfuse-web:3000/"),
    timedProbe("dify-web", "http://dify-web:3000/"),
    timedProbe("dify-api", "http://dify-api:5001/health"),
  ]);

  const [ollama, qdrant, coreMetrics] = await Promise.all([
    timedJson(`${OLLAMA_BASE_URL}/api/tags`, 2200),
    timedJson("http://qdrant:6333/collections", 2200),
    timedJson("http://core:8100/metrics", 2200, getCoreAuthHeaders()),
  ]);
  const appleLLM = APPLE_LLM_ENABLED && APPLE_LLM_BASE_URL
    ? await timedJson(`${APPLE_LLM_BASE_URL}/health`, 2200)
    : null;

  const ollamaModels = Array.isArray(ollama.json?.models) ? ollama.json.models.length : 0;
  const ollamaModelNames = Array.isArray(ollama.json?.models)
    ? ollama.json.models
        .map((model: { name?: unknown }) => (typeof model?.name === "string" ? model.name : ""))
        .filter((name: string) => !!name)
    : [];
  const qdrantCollections = Array.isArray(qdrant.json?.result?.collections)
    ? qdrant.json.result.collections.length
    : 0;

  return {
    timestamp: new Date().toISOString(),
    gateway: {
      api: { ok: true, status: 200 },
      core: probes.find((p) => p.name === "core")?.ok ?? false,
    },
    ai: {
      ollama: {
        ok: ollama.ok,
        status: ollama.status,
        latency_ms: ollama.latencyMs,
        models: ollamaModels,
        model_names: ollamaModelNames,
        error: ollama.error,
      },
      apple_llm: appleLLM ? {
        ok: appleLLM.ok,
        status: appleLLM.status,
        latency_ms: appleLLM.latencyMs,
        backend: appleLLM.json?.backend ?? null,
        model_id: appleLLM.json?.model_id ?? null,
        runtime_ready: appleLLM.json?.runtime_ready ?? null,
        error: appleLLM.error ?? appleLLM.json?.runtime_error,
      } : null,
      qdrant: {
        ok: qdrant.ok,
        status: qdrant.status,
        latency_ms: qdrant.latencyMs,
        collections: qdrantCollections,
        error: qdrant.error,
      },
    },
    services: probes,
    core_metrics: {
      ok: coreMetrics.ok,
      status: coreMetrics.status,
      data: coreMetrics.json ?? null,
      error: coreMetrics.error,
    },
  };
}

function getNumberParam(value: string | undefined, fallback: number, max: number): number {
  const parsed = Number.parseInt(value || "", 10);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return Math.min(parsed, max);
}

const ops = new Hono();

ops.get("/monitor", async (c) => c.json(await collectMonitorSnapshot()));

ops.get("/sources", async (c) =>
  c.json(
    await (async () => {
      const [opsAgentSources, loki] = await Promise.all([
        opsAgentJson("/sources"),
        lokiReady(),
      ]);

      return {
        service_monitor: { available: true, kind: "http-probe" },
        agent_traces: { available: true, kind: "native-trace" },
        machine_logs: {
          available: !!opsAgentSources.json?.journald?.available,
          kind: opsAgentSources.json?.journald?.kind || "ops-agent",
        },
        docker_events: {
          available: !!opsAgentSources.json?.docker_events?.available,
          kind: opsAgentSources.json?.docker_events?.kind || "ops-agent",
        },
        docker_logs: {
          available: !!opsAgentSources.json?.docker_logs?.available,
          kind: opsAgentSources.json?.docker_logs?.kind || "ops-agent",
        },
        loki_history: { available: loki, kind: "loki" },
        otel: {
          available: (process.env.OTEL_ENABLED || "").toLowerCase() === "true",
          kind: "otlp-http",
        },
        agentsight: {
          available: !!opsAgentSources.json?.agentsight?.available,
          kind: "optional-complement",
        },
      };
    })(),
  ),
);

ops.get("/summary", async (c) => {
  try {
    const [monitor, traces, opsAgent, loki, clusterIdentity, clusterPeers] = await Promise.all([
      collectMonitorSnapshot(),
      coreClient.recentAgentTraces({ limit: 60 }),
      opsAgentJson("/summary"),
      lokiReady(),
      coreClient.clusterIdentity().catch(() => null),
      coreClient.clusterPeers().catch(() => null),
    ]);
    const mcp = isRecord(opsAgent.json?.mcp)
      ? (opsAgent.json.mcp as McpSuiteStatus)
      : await probeMcpRuntime().catch((error) => ({
          ok: false,
          status: "failed" as const,
          aggregate_status: "failed" as const,
          requested_runtime: "auto",
          runtime_mode: null,
          protocol_version: null,
          server_name: null,
          tool_count: 0,
          resource_count: 0,
          prompt_count: 0,
          latency_ms: 0,
          checks: [],
          primary_server: "kicad",
          primary: makeDefaultMcpStatus({ requested_runtime: "auto" }),
          server_count: 0,
          servers_ok: 0,
          degraded_servers: [],
          servers: {},
          error: error instanceof Error ? error.message : "MCP probe failed",
        }));

    const recentRuns = Array.from(
      new Map(
        traces.events
          .filter((event) => event.run_id)
          .map((event) => [event.run_id, event]),
      ).values(),
    ).slice(-10).reverse();

    const activeRuns = new Set(
      traces.events
        .filter((event) => event.event_type === "run_started")
        .map((event) => event.run_id),
    );
    for (const event of traces.events) {
      if (event.event_type === "run_completed" || event.event_type === "run_failed") {
        activeRuns.delete(event.run_id);
      }
    }

    return c.json({
      timestamp: monitor.timestamp,
      monitor,
      traces: {
        total_recent: traces.count,
        active_runs: activeRuns.size,
        recent_runs: recentRuns.map((event) => ({
          run_id: event.run_id,
          mode: event.mode,
          agent_name: event.agent_name,
          event_type: event.event_type,
          ts: event.ts,
          message: event.message,
        })),
      },
      alerts: sortLogs([
        ...traces.events
          .filter((event) => event.severity === "error" || event.severity === "critical")
          .map(traceToLogEntry),
        ...monitor.services
          .map((probe) => probeToLogEntry(probe, monitor.timestamp))
          .filter((entry): entry is OpsLogEntry => entry !== null),
        ...((Array.isArray(opsAgent.json?.recent?.entries) ? opsAgent.json.recent.entries : [])
          .filter((entry: OpsLogEntry) =>
            entry.severity === "warning" ||
            entry.severity === "error" ||
            entry.severity === "critical"
          )
          .slice(0, 20)),
      ]).slice(0, 25),
      sources: {
        service_monitor: true,
        agent_traces: true,
        machine_logs: !!opsAgent.json?.sources?.journald?.available,
        docker_events: !!opsAgent.json?.sources?.docker_events?.available,
        loki_history: loki,
        otel: (process.env.OTEL_ENABLED || "").toLowerCase() === "true",
        agentsight: !!opsAgent.json?.sources?.agentsight?.available,
      },
      cluster: {
        enabled: !!clusterIdentity?.cluster_enabled,
        node_id: clusterIdentity?.node_id || null,
        role: clusterIdentity?.role || null,
        peers_total: clusterPeers?.peers?.length || 0,
        peers_ok: clusterPeers?.peers?.filter((peer) => peer.ok).length || 0,
      },
      mcp,
      ops_agent: opsAgent.json ?? null,
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

ops.get("/agent-traces/recent", async (c) => {
  try {
    const query = c.req.query();
    const result = await coreClient.recentAgentTraces({
      limit: getNumberParam(query.limit, 50, 500),
      run_id: query.run_id,
      agent_name: query.agent_name,
      event_type: query.event_type,
    });
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

ops.get("/agent-traces/stream", async (c) => {
  try {
    const search = new URL(c.req.url).search;
    return await proxySseResponse(
      `${CORE_URL}/agent-traces/stream${search}`,
      getCoreAuthHeaders(),
      c.req.raw.signal,
    );
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

ops.get("/agent-traces/:runId", async (c) => {
  try {
    const runId = c.req.param("runId");
    const limit = getNumberParam(c.req.query("limit"), 200, 1000);
    const result = await coreClient.runAgentTraces(runId, limit);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

ops.get("/logs/recent", async (c) => {
  try {
    const query = c.req.query();
    const source = query.source || "all";
    const minSeverity = coerceSeverity(query.severity) || "info";
    const limit = getNumberParam(query.limit, 80, 400);

    const [monitor, traces, opsAgentLogs, opsAgentEvents] = await Promise.all([
      collectMonitorSnapshot(),
      coreClient.recentAgentTraces({
        limit,
        run_id: query.run_id,
        agent_name: query.agent_name,
        event_type: query.event_type,
      }),
      source === "all" || source === "service" || source === "machine"
        ? opsAgentJson(
            `/logs/recent?limit=${encodeURIComponent(String(limit))}&include_services=${encodeURIComponent(
              String(source === "all" || source === "service"),
            )}&include_machine=${encodeURIComponent(
              String(source === "all" || source === "machine"),
            )}${query.service ? `&services=${encodeURIComponent(query.service)}` : ""}${
              query.include_routine ? `&include_routine=${encodeURIComponent(query.include_routine)}` : ""
            }`,
            3200,
          )
        : Promise.resolve({ ok: false, status: 0, latencyMs: 0, json: undefined } as TimedJsonResult),
      source === "all" || source === "docker-event"
        ? opsAgentJson(
            `/events/recent?limit=${encodeURIComponent(String(limit))}&since_seconds=900${
              query.include_routine ? `&include_routine=${encodeURIComponent(query.include_routine)}` : ""
            }`,
            3200,
          )
        : Promise.resolve({ ok: false, status: 0, latencyMs: 0, json: undefined } as TimedJsonResult),
    ]);

    const entries: OpsLogEntry[] = [];

    if (source === "all" || source === "agent-trace") {
      entries.push(...traces.events.map(traceToLogEntry));
    }
    if (source === "all" || source === "service") {
      entries.push(
        ...monitor.services
          .map((probe) => probeToLogEntry(probe, monitor.timestamp))
          .filter((entry): entry is OpsLogEntry => entry !== null),
      );
      if (!monitor.core_metrics.ok) {
        entries.push({
          id: `core-metrics:${monitor.timestamp}`,
          ts: monitor.timestamp,
          source: "service",
          service: "core-metrics",
          severity: "warning",
          message: monitor.core_metrics.error
            ? `core metrics unavailable: ${monitor.core_metrics.error}`
            : `core metrics unavailable (${monitor.core_metrics.status})`,
        });
      }
    }
    if ((source === "all" || source === "service" || source === "machine") && Array.isArray(opsAgentLogs.json?.entries)) {
      entries.push(
        ...opsAgentLogs.json.entries.map((entry: OpsLogEntry) => ({
          ...entry,
          source: entry.source === "machine" ? "machine" : "service",
        })),
      );
    }
    if ((source === "all" || source === "docker-event") && Array.isArray(opsAgentEvents.json?.events)) {
      entries.push(
        ...opsAgentEvents.json.events.filter((entry: OpsLogEntry) => {
          if (!query.service?.trim()) {
            return true;
          }
          return entry.service === query.service.trim();
        }),
      );
    }

    const filtered = sortLogs(entries)
      .filter((entry) => severityRank(entry.severity) >= severityRank(minSeverity))
      .filter((entry) =>
        labelsMatchRouting(entry, {
          routing_role: query.routing_role,
          routing_provider: query.routing_provider,
          routing_model: query.routing_model,
        }),
      )
      .slice(0, limit);

    return c.json({
      entries: filtered,
      count: filtered.length,
      timestamp: monitor.timestamp,
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

ops.get("/logs/stream", async (c) => {
  try {
    const search = new URL(c.req.url).search;
    return await proxySseResponse(
      `${OPS_AGENT_URL}/logs/stream${search}`,
      undefined,
      c.req.raw.signal,
    );
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "Ops Agent stream failed" },
      503,
    );
  }
});

ops.get("/logs/query", async (c) => {
  try {
    const query = c.req.query();
    const entries = await queryLoki({
      source: query.source,
      limit: getNumberParam(query.limit, 120, 400),
      query: query.q,
      run_id: query.run_id,
      agent_name: query.agent_name,
      event_type: query.event_type,
      service: query.service,
      severity: coerceSeverity(query.severity),
      since: query.since,
    });
    const filtered = entries.filter((entry) =>
      labelsMatchRouting(entry, {
        routing_role: query.routing_role,
        routing_provider: query.routing_provider,
        routing_model: query.routing_model,
      }),
    );
    return c.json({
      entries: filtered,
      count: filtered.length,
      source: "loki",
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    return c.json(
      { error: error instanceof Error ? error.message : "Loki query failed" },
      503,
    );
  }
});

export { ops };
