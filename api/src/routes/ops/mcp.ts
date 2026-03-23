import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { Hono } from "hono";
import { handleCoreError } from "../../middleware/error.js";
import {
  type McpProbeConfig,
  type McpProbePayload,
  type McpRuntimeStatus,
  type McpSuiteStatus,
  isRecord,
  opsAgentJson,
  KILL_LIFE_ROOT,
  KILL_LIFE_MCP_SMOKE,
  KILL_LIFE_VALIDATE_SPECS_MCP_SMOKE,
  KILL_LIFE_KNOWLEDGE_BASE_MCP_SMOKE,
  KILL_LIFE_GITHUB_DISPATCH_MCP_SMOKE,
} from "./_shared.js";

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
    key: "knowledge-base",
    command: ["python3", KILL_LIFE_KNOWLEDGE_BASE_MCP_SMOKE, "--json", "--quick", "--timeout", "8.0"],
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

export function makeDefaultMcpStatus(overrides: Partial<McpRuntimeStatus> = {}): McpRuntimeStatus {
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

function makeFailedMcpSuiteStatus(message: string): McpSuiteStatus {
  const primary = makeDefaultMcpStatus({
    requested_runtime: "auto",
    server_name: "kicad",
    status: "failed",
    error: message,
  });
  return {
    ...primary,
    ok: false,
    status: "failed",
    aggregate_status: "failed",
    primary_server: "kicad",
    primary,
    server_count: 0,
    servers_ok: 0,
    degraded_servers: [],
    servers: {},
  };
}

export async function fetchOpsAgentMcpSummary(force: boolean = false): Promise<McpSuiteStatus> {
  const suffix = force ? "?force=true" : "";
  const result = await opsAgentJson(`/mcp/summary${suffix}`, 9000);
  if (isRecord(result.json)) {
    return result.json as McpSuiteStatus;
  }
  return makeFailedMcpSuiteStatus(
    result.error || `Ops Agent MCP summary unavailable (${result.status || 0})`,
  );
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

export async function probeMcpRuntime(timeoutMs: number = 8000): Promise<McpSuiteStatus> {
  const now = Date.now();
  if (cachedMcpProbe && cachedMcpProbe.expiresAt > now) {
    return cachedMcpProbe.value;
  }
  if (inflightMcpProbe) {
    return await inflightMcpProbe;
  }

  inflightMcpProbe = (async () => {
    const hardTimeoutMs = Math.max(1000, timeoutMs);
    let timeoutHandle: NodeJS.Timeout | null = null;
    const timeoutResult = new Promise<readonly (readonly [string, McpRuntimeStatus])[]>((resolve) => {
      timeoutHandle = setTimeout(() => {
        resolve(
          MCP_PROBE_CONFIGS.map((config) => [
            config.key,
            makeDefaultMcpStatus({
              status: "degraded",
              server_name: config.key,
              error: `Global MCP probe timeout after ${(hardTimeoutMs / 1000).toFixed(1)}s`,
            }),
          ] as const),
        );
      }, hardTimeoutMs);
      timeoutHandle.unref?.();
    });

    const probeResult = Promise.allSettled(
      MCP_PROBE_CONFIGS.map(async (config) => [config.key, await runMcpProbe(config)] as const),
    ).then((results) =>
      results.map((result, idx) => {
        if (result.status === "fulfilled") {
          return result.value;
        }
        const failedConfig = MCP_PROBE_CONFIGS[idx];
        return [
          failedConfig.key,
          makeDefaultMcpStatus({
            status: "degraded",
            server_name: failedConfig.key,
            error: `Probe error: ${String(result.reason || "unknown")}`,
          }),
        ] as const;
      }),
    );
    const statuses = await Promise.race([probeResult, timeoutResult]);
    if (timeoutHandle) {
      clearTimeout(timeoutHandle);
    }
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

// ── Routes ─────────────────────────────────────────────────────────────────

const mcpRoutes = new Hono();

mcpRoutes.post("/mcp/probe/:serverKey", async (c) => {
  try {
    const serverKey = c.req.param("serverKey");
    const force = (c.req.query("force") || "true").toLowerCase() !== "false";
    const suite = await fetchOpsAgentMcpSummary(force);
    const server = suite.servers?.[serverKey];

    if (!server) {
      return c.json(
        {
          error: `Unknown MCP server '${serverKey}'`,
          available_servers: Object.keys(suite.servers || {}),
        },
        404,
      );
    }

    return c.json({
      server_key: serverKey,
      aggregate_status: suite.aggregate_status,
      server_count: suite.server_count,
      degraded_servers: suite.degraded_servers,
      ...server,
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { mcpRoutes };
