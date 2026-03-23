import { request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { existsSync } from "node:fs";
import path from "node:path";
import {
  coreClient,
  getCoreAuthHeaders,
  type AgentTraceEvent,
} from "../../client/core.js";

// ── Types ──────────────────────────────────────────────────────────────────

export type ProbeResult = {
  name: string;
  url: string;
  ok: boolean;
  status: number;
  latency_ms: number;
  error?: string;
};

export type TimedJsonResult = {
  ok: boolean;
  status: number;
  latencyMs: number;
  json?: any;
  error?: string;
};

export type OpsLogEntry = {
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

export type MonitorSnapshot = {
  timestamp: string;
  gateway: {
    api: { ok: boolean; status: number };
    core: boolean;
  };
  observability: {
    traces_backend: "tempo";
    logs_backend: "loki";
    metrics_backend: "prometheus";
    tempo: ProbeResult | null;
    grafana_proxy_url: string;
    langfuse_proxy_url: string;
  };
  public: {
    proxy_enabled: boolean;
    bind_host: string;
    public_bind: boolean;
    server_name: string;
    auth_configured: boolean;
    surfaces: Array<{
      name: string;
      host: string;
      url: string;
      protected: boolean;
      ok: boolean;
      status: number;
      latency_ms: number;
      note: string;
      error?: string;
    }>;
  };
  industrial: {
    ui: {
      host: string;
      url: string;
      ok: boolean;
      status: number;
      latency_ms: number;
      note: string;
      error?: string;
    } | null;
    summary: {
      server_count: number;
      runtime_ok_count: number;
      runtime_error_count: number;
      topology_valid: boolean;
      vendor_contract_ready_count: number;
      vendor_contract_blocked_count: number;
      cockpit_service_ok: boolean;
      cockpit_proxy_ok: boolean;
    };
    servers: Array<{
      key: string;
      label: string;
      description: string;
      ok: boolean;
      runtime_ok: boolean;
      protocol_version?: string;
      tool_count: number;
      resource_count: number;
      prompt_count: number;
      error?: string;
      health?: Record<string, unknown>;
      contract?: Record<string, unknown>;
    }>;
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

export type McpProbePayload = {
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

export type McpRuntimeStatus = {
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

export type McpSuiteStatus = McpRuntimeStatus & {
  aggregate_status: "ready" | "degraded" | "failed";
  primary_server: string;
  primary: McpRuntimeStatus;
  server_count: number;
  servers_ok: number;
  degraded_servers: string[];
  servers: Record<string, McpRuntimeStatus>;
};

export type McpProbeConfig = {
  key: string;
  command: string[];
  cwd: string;
  timeout_ms: number;
  primary?: boolean;
};

type DecodedLokiLine = {
  line: string;
  structured: Record<string, unknown> | null;
  envelopeTs?: string;
};

// ── Constants ──────────────────────────────────────────────────────────────

export const OLLAMA_BASE_URL = (process.env.OLLAMA_BASE_URL || "http://ollama:11434").replace(/\/+$/, "");
export const APPLE_LLM_ENABLED = (process.env.APPLE_LLM_ENABLED || "").toLowerCase() === "true";
export const APPLE_LLM_BASE_URL = (process.env.APPLE_LLM_BASE_URL || "").replace(/\/+$/, "");
export const OPS_AGENT_URL = (process.env.OPS_AGENT_URL || "http://ops-agent:9200").replace(/\/+$/, "");
export const LOKI_URL = (process.env.LOKI_URL || "http://loki:3100").replace(/\/+$/, "");
export const CORE_URL = (process.env.CORE_URL || "http://core:8100").replace(/\/+$/, "");
export const EDGE_PROXY_BIND_HOST = (process.env.EDGE_PROXY_BIND_HOST || "127.0.0.1").trim();
export const EDGE_PROXY_SERVER_NAME = (process.env.EDGE_PROXY_SERVER_NAME || "localhost").trim();
export const EDGE_PROXY_GRAFANA_SERVER_NAME = (
  process.env.EDGE_PROXY_GRAFANA_SERVER_NAME || `grafana.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_LANGFUSE_SERVER_NAME = (
  process.env.EDGE_PROXY_LANGFUSE_SERVER_NAME || `langfuse.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_OLLAMA_SERVER_NAME = (
  process.env.EDGE_PROXY_OLLAMA_SERVER_NAME || `ollama.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_PROMETHEUS_SERVER_NAME = (
  process.env.EDGE_PROXY_PROMETHEUS_SERVER_NAME || `prometheus.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_MEM0_SERVER_NAME = (
  process.env.EDGE_PROXY_MEM0_SERVER_NAME || `mem0.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_FIRECRAWL_SERVER_NAME = (
  process.env.EDGE_PROXY_FIRECRAWL_SERVER_NAME || `firecrawl.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_SEARCH_SERVER_NAME = (
  process.env.EDGE_PROXY_SEARCH_SERVER_NAME || `search.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_PAPERLESS_SERVER_NAME = (
  process.env.EDGE_PROXY_PAPERLESS_SERVER_NAME || `paperless.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_KARAKEEP_SERVER_NAME = (
  process.env.EDGE_PROXY_KARAKEEP_SERVER_NAME || `karakeep.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_ZEROCLAW_SERVER_NAME = (
  process.env.EDGE_PROXY_ZEROCLAW_SERVER_NAME || `zeroclaw.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_ZEROCLAW_DOCS_SERVER_NAME = (
  process.env.EDGE_PROXY_ZEROCLAW_DOCS_SERVER_NAME || `zeroclaw-docs.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_LANGGRAPH_SERVER_NAME = (
  process.env.EDGE_PROXY_LANGGRAPH_SERVER_NAME || `langgraph.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const EDGE_PROXY_INDUSTRIAL_SERVER_NAME = (
  process.env.EDGE_PROXY_INDUSTRIAL_SERVER_NAME || `industrial.${EDGE_PROXY_SERVER_NAME}`
).trim();
export const ZEROCLAW_GATEWAY_URL = (
  process.env.ZEROCLAW_GATEWAY_URL || "http://host.docker.internal:3000"
).replace(/\/+$/, "");
export const ZEROCLAW_FOLLOW_URL = (
  process.env.ZEROCLAW_FOLLOW_URL || "http://host.docker.internal:8788"
).replace(/\/+$/, "");
export const GRAFANA_PUBLIC_ORIGIN = (
  process.env.GRAFANA_PUBLIC_ORIGIN || `https://${EDGE_PROXY_GRAFANA_SERVER_NAME}`
).replace(/\/+$/, "");
export const LANGFUSE_PUBLIC_ORIGIN = (
  process.env.LANGFUSE_PUBLIC_ORIGIN || `https://${EDGE_PROXY_LANGFUSE_SERVER_NAME}`
).replace(/\/+$/, "");
export const EDGE_PROXY_OPS_AUTH_USER = (process.env.EDGE_PROXY_OPS_AUTH_USER || "").trim();
export const EDGE_PROXY_OPS_AUTH_PASSWORD = process.env.EDGE_PROXY_OPS_AUTH_PASSWORD || "";
export const EDGE_PROXY_INDUSTRIAL_GROUPS = (
  process.env.EDGE_PROXY_INDUSTRIAL_GROUPS || "operator"
).trim();
export const KILL_LIFE_ROOT = path.resolve(process.env.KILL_LIFE_ROOT || "/home/clems/Kill_LIFE");
export const KILL_LIFE_MCP_SMOKE = path.join(KILL_LIFE_ROOT, "tools", "hw", "mcp_smoke.py");
export const KILL_LIFE_VALIDATE_SPECS_MCP_SMOKE = path.join(
  KILL_LIFE_ROOT,
  "tools",
  "validate_specs_mcp_smoke.py",
);
export const KILL_LIFE_KNOWLEDGE_BASE_MCP_SMOKE = path.join(
  KILL_LIFE_ROOT,
  "tools",
  "knowledge_base_mcp_smoke.py",
);
export const KILL_LIFE_GITHUB_DISPATCH_MCP_SMOKE = path.join(
  KILL_LIFE_ROOT,
  "tools",
  "github_dispatch_mcp_smoke.py",
);

// ── Utility Functions ──────────────────────────────────────────────────────

export async function timedJson(
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

export async function timedProbe(
  name: string,
  url: string,
  timeoutMs: number = 1500,
  acceptedStatuses: number[] = [],
  headers?: Record<string, string>,
): Promise<ProbeResult> {
  if (headers && Object.keys(headers).some((key) => key.toLowerCase() === "host")) {
    const started = Date.now();
    try {
      const target = new URL(url);
      const requester = target.protocol === "https:" ? httpsRequest : httpRequest;
      const response = await new Promise<{ status: number }>((resolve, reject) => {
        const req = requester(
          {
            protocol: target.protocol,
            hostname: target.hostname,
            port: target.port || (target.protocol === "https:" ? 443 : 80),
            path: `${target.pathname}${target.search}`,
            method: "GET",
            headers,
            rejectUnauthorized: false,
          },
          (res) => {
            res.resume();
            resolve({ status: res.statusCode || 0 });
          },
        );
        req.setTimeout(timeoutMs, () => req.destroy(new Error("timeout")));
        req.on("error", reject);
        req.end();
      });
      const ok = response.status >= 200 && response.status < 300 || acceptedStatuses.includes(response.status);
      return {
        name,
        url,
        ok,
        status: response.status,
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
    }
  }

  const started = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { headers, signal: controller.signal });
    const ok = res.ok || acceptedStatuses.includes(res.status);
    return {
      name,
      url,
      ok,
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

export function proxyAuthHeaders(host: string): Record<string, string> {
  const headers: Record<string, string> = { Host: host };
  if (EDGE_PROXY_OPS_AUTH_USER && EDGE_PROXY_OPS_AUTH_PASSWORD) {
    headers.Authorization = `Basic ${Buffer.from(
      `${EDGE_PROXY_OPS_AUTH_USER}:${EDGE_PROXY_OPS_AUTH_PASSWORD}`,
    ).toString("base64")}`;
  }
  return headers;
}

export function industrialCockpitHeaders(): Record<string, string> {
  return {
    "X-Forwarded-User": "ops",
    "X-Forwarded-Email": "ops",
    "X-Forwarded-Groups": EDGE_PROXY_INDUSTRIAL_GROUPS,
  };
}

export function isProxyPublic(): boolean {
  return !["127.0.0.1", "localhost", "::1"].includes(EDGE_PROXY_BIND_HOST);
}

export function isRecord(value: unknown): value is Record<string, unknown> {
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

export function coerceSource(value: unknown, fallback: OpsLogEntry["source"]): OpsLogEntry["source"] {
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

export function coerceOptionalString(value: unknown): string | undefined {
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
      ...(coerceOptionalString(decoded.structured.routing_policy)
        ? { routing_policy: coerceOptionalString(decoded.structured.routing_policy)! }
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

export function severityRank(severity: OpsLogEntry["severity"]): number {
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

export function labelsMatchRouting(
  entry: OpsLogEntry,
  filters: {
    routing_role?: string;
    routing_provider?: string;
    routing_model?: string;
    routing_policy?: string;
  },
): boolean {
  const role = filters.routing_role?.trim().toLowerCase();
  const provider = filters.routing_provider?.trim().toLowerCase();
  const model = filters.routing_model?.trim().toLowerCase();
  const policy = filters.routing_policy?.trim().toLowerCase();
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
  if (policy && (labels.routing_policy || "").trim().toLowerCase() !== policy) {
    return false;
  }
  return true;
}

export function coerceSeverity(value: string | undefined): OpsLogEntry["severity"] | null {
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

export function traceToLogEntry(event: AgentTraceEvent): OpsLogEntry {
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
      routing_policy: event.routing_policy ?? "",
    },
  };
}

export function probeToLogEntry(probe: ProbeResult, timestamp: string): OpsLogEntry | null {
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

export function sortLogs(entries: OpsLogEntry[]): OpsLogEntry[] {
  return [...entries].sort((left, right) => {
    const tsDiff = new Date(right.ts).getTime() - new Date(left.ts).getTime();
    if (tsDiff !== 0) return tsDiff;
    return severityRank(right.severity) - severityRank(left.severity);
  });
}

export async function opsAgentJson(
  path: string,
  timeoutMs: number = 2200,
): Promise<TimedJsonResult> {
  return timedJson(`${OPS_AGENT_URL}${path}`, timeoutMs);
}

export async function proxySseResponse(
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

export async function lokiReady(timeoutMs: number = 1600): Promise<boolean> {
  const result = await timedJson(`${LOKI_URL}/ready`, timeoutMs);
  return result.ok;
}

export function inferSeverityFromMessage(message: string): OpsLogEntry["severity"] {
  if (/\b(critical|fatal|panic)\b/i.test(message)) return "critical";
  if (/\b(error|exception|traceback|failed)\b/i.test(message)) return "error";
  if (/\b(warn|warning)\b/i.test(message)) return "warning";
  if (/\b(debug|trace)\b/i.test(message)) return "debug";
  return "info";
}

export function parseSinceWindow(value: string | undefined): number {
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

export function getNumberParam(value: string | undefined, fallback: number, max: number): number {
  const parsed = Number.parseInt(value || "", 10);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return Math.min(parsed, max);
}

// Re-export coreClient and getCoreAuthHeaders for convenience
export { coreClient, getCoreAuthHeaders };
