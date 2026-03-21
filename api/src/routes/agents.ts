import { Hono, type Context } from "hono";
import { CoreApiError, coreClient } from "../client/core.js";
import { emitStructuredLog } from "../lib/otel.js";
import { handleCoreError } from "../middleware/error.js";
import {
  AgentCreateRequestSchema,
  AgentUpdateRequestSchema,
} from "../validation/index.js";

const agents = new Hono();
const SAFE_NAME_RE = /^[\w.-]+$/;
const OPS_AGENT_URL = (process.env.OPS_AGENT_URL || "http://ops-agent:9200").replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 15_000;

type JsonBody = Record<string, unknown> | null;
type ProviderMutationResponse = {
  status: string;
  active: boolean;
  configured: boolean;
  message?: string;
  updated_env?: string[];
  cleared_env?: string[];
  restarted_services?: string[];
};
type OperatorCopilotLog = {
  ts?: string;
  source?: string;
  service?: string;
  severity?: string;
  message?: string;
  run_id?: string;
  agent_name?: string | null;
  event_type?: string;
};
type OperatorCopilotTrace = {
  ts?: string;
  agent_name?: string | null;
  event_type?: string;
  message?: string;
  routing_role?: string | null;
  routing_provider?: string | null;
  routing_model?: string | null;
  routing_policy?: string | null;
  error?: string | null;
};
type OperatorCopilotRequest = {
  mode?: string;
  prompt?: string;
  run_id?: string;
  service?: string;
  severity?: string;
  mcp_server?: string;
  window?: string;
  logs?: OperatorCopilotLog[];
  traces?: OperatorCopilotTrace[];
};

function parseJsonBody(text: string): JsonBody {
  if (!text.trim()) {
    return null;
  }
  try {
    const parsed = JSON.parse(text);
    return typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function requestHeaders(c: Context, body?: unknown): Headers {
  const headers = new Headers();
  const authHeader = c.req.header("Authorization");
  const cookieHeader = c.req.header("Cookie");
  if (authHeader) {
    headers.set("Authorization", authHeader);
  }
  if (cookieHeader) {
    headers.set("Cookie", cookieHeader);
  }
  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

function jsonWithStatus(c: Context, body: Record<string, unknown>, status: number) {
  return c.newResponse(JSON.stringify(body), status as any, {
    "Content-Type": "application/json",
  });
}

function syncProviderEnvFromUpdate(values: Record<string, unknown>) {
  for (const [key, value] of Object.entries(values)) {
    process.env[key] = String(value);
  }
}

function syncProviderEnvFromClear(fields: string[]) {
  for (const key of fields) {
    process.env[key] = "";
  }
}

function asTrimmedString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function clipLines(lines: string[], max: number): string[] {
  return lines.filter(Boolean).slice(0, max);
}

function buildOperatorCopilotPrompt(body: OperatorCopilotRequest): string {
  const sections: string[] = [
    "Tu es Agent Zero en mode operator copilot.",
    "Ta mission: cadrer l'incident ou le run observe, prioriser les causes probables, proposer les prochaines actions manuelles les plus sures, et signaler clairement ce qui est seulement hypothese.",
    "Ne lance aucune action implicite. Pas de blabla.",
  ];

  const contextLines = clipLines(
    [
      body.mode ? `mode: ${body.mode}` : "",
      body.run_id ? `run_id: ${body.run_id}` : "",
      body.service ? `service: ${body.service}` : "",
      body.severity ? `severity: ${body.severity}` : "",
      body.mcp_server ? `mcp_server: ${body.mcp_server}` : "",
      body.window ? `window: ${body.window}` : "",
    ],
    12,
  );
  if (contextLines.length > 0) {
    sections.push(`Contexte operateur:\n${contextLines.join("\n")}`);
  }

  const logLines = clipLines(
    (Array.isArray(body.logs) ? body.logs : []).map((entry) => {
      const parts = [
        asTrimmedString(entry.ts),
        asTrimmedString(entry.source),
        asTrimmedString(entry.service),
        asTrimmedString(entry.severity),
        asTrimmedString(entry.event_type),
        asTrimmedString(entry.agent_name || undefined),
        asTrimmedString(entry.run_id),
      ].filter(Boolean);
      return `${parts.join(" | ")} :: ${asTrimmedString(entry.message) || "(no message)"}`;
    }),
    18,
  );
  if (logLines.length > 0) {
    sections.push(`Logs recents:\n${logLines.join("\n")}`);
  }

  const traceLines = clipLines(
    (Array.isArray(body.traces) ? body.traces : []).map((entry) => {
      const parts = [
        asTrimmedString(entry.ts),
        asTrimmedString(entry.agent_name || undefined),
        asTrimmedString(entry.event_type),
        asTrimmedString(entry.routing_role || undefined),
        asTrimmedString(entry.routing_provider || undefined),
        asTrimmedString(entry.routing_model || undefined),
        asTrimmedString(entry.routing_policy || undefined),
      ].filter(Boolean);
      const error = asTrimmedString(entry.error || undefined);
      return `${parts.join(" | ")} :: ${asTrimmedString(entry.message) || "(no message)"}${error ? ` / error: ${error}` : ""}`;
    }),
    18,
  );
  if (traceLines.length > 0) {
    sections.push(`Traces recentes:\n${traceLines.join("\n")}`);
  }

  if (body.prompt && body.prompt.trim()) {
    sections.push(`Demande operateur:\n${body.prompt.trim()}`);
  } else {
    sections.push(
      "Demande operateur:\nResume la situation, liste les causes probables, les verifications immediates et la prochaine action manuelle recommandee.",
    );
  }

  sections.push(
    "Format de reponse attendu:\n1. Situation\n2. Causes probables\n3. Verifications immediates\n4. Prochaine action recommandee\n5. Risques / points incertains",
  );
  return sections.join("\n\n");
}

async function proxyOpsAgentJson(
  c: Context,
  path: string,
  init: RequestInit = {},
): Promise<{ upstream: Response; text: string; json: JsonBody }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const upstream = await fetch(`${OPS_AGENT_URL}${path}`, {
      ...init,
      headers: requestHeaders(c, init.body),
      signal: controller.signal,
    });
    const text = await upstream.text();
    return { upstream, text, json: parseJsonBody(text) };
  } finally {
    clearTimeout(timer);
  }
}

async function providerMutationResult(
  c: Context,
  name: string,
  path: string,
  init: RequestInit,
) {
  const { upstream, text, json } = await proxyOpsAgentJson(c, path, init);
  if (!upstream.ok) {
    return {
      response: jsonWithStatus(c, json || { error: text || "Ops Agent request failed" }, upstream.status),
      payload: null as ProviderMutationResponse | null,
    };
  }

  let active = false;
  let configured = false;
  try {
    const status = await coreClient.providersStatus();
    const provider = status.providers.find((entry) => entry.name === name);
    active = !!provider?.active;
    configured = !!provider?.configured;
  } catch {
    // Keep the durable write result even if the post-restart status probe fails.
  }

  const body: ProviderMutationResponse = {
    status: "ok",
    active,
    configured,
  };
  if (typeof json?.message === "string") {
    body.message = json.message;
  } else if (!active) {
    body.message = configured
      ? "Saved but provider inactive"
      : "Saved but provider reports not configured";
  }
  if (Array.isArray(json?.updated_env)) {
    body.updated_env = json.updated_env as string[];
  }
  if (Array.isArray(json?.cleared_env)) {
    body.cleared_env = json.cleared_env as string[];
  }
  if (Array.isArray(json?.restarted_services)) {
    body.restarted_services = json.restarted_services as string[];
  }
  return {
    response: c.json(body),
    payload: body,
  };
}

/** Lister tous les agents */
agents.get("/", async (c) => {
  try {
    const result = await coreClient.listAgents();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Creer un agent */
agents.post("/", async (c) => {
  try {
    let raw: unknown;
    try {
      raw = await c.req.json();
    } catch {
      return c.json({ error: "Validation failed", details: [{ message: "Request body is not valid JSON" }] }, 400);
    }
    const parsed = AgentCreateRequestSchema.safeParse(raw);
    if (!parsed.success) {
      return c.json({
        error: "Validation failed",
        details: parsed.error.issues.map((issue: { path: (string | number)[]; message: string; code: string }) => ({
          path: issue.path.join("."),
          message: issue.message,
          code: issue.code,
        })),
      }, 400);
    }
    const body = parsed.data;
    const result = await coreClient.createAgent(body);
    return c.json(result, 201);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Executer un agent */
agents.post("/:name/run", async (c) => {
  try {
    const name = c.req.param("name");
    if (!name || !SAFE_NAME_RE.test(name)) {
      return c.json({ error: "Invalid agent name" }, 400);
    }
    const { messages } = await c.req.json();
    const result = await coreClient.runAgent(name, messages);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

agents.post("/agent-zero/copilot", async (c) => {
  try {
    const body = (await c.req.json()) as OperatorCopilotRequest;
    const prompt = buildOperatorCopilotPrompt(body);
    const result = await coreClient.runAgent("agent-zero", [{ role: "user", content: prompt }]);
    emitStructuredLog({
      source: "agent-trace",
      service: "api",
      severity: "info",
      message: "agent-zero operator copilot completed",
      run_id: body.run_id,
      agent_name: "agent-zero",
      event_type: "operator_copilot_completed",
      mode: body.mode || "operator-copilot",
    });
    return c.json({
      ...result,
      operator_context: {
        mode: body.mode || "operator-copilot",
        run_id: body.run_id || null,
        service: body.service || null,
        severity: body.severity || null,
        mcp_server: body.mcp_server || null,
        log_count: Array.isArray(body.logs) ? body.logs.length : 0,
        trace_count: Array.isArray(body.traces) ? body.traces.length : 0,
      },
    });
  } catch (error) {
    emitStructuredLog({
      source: "agent-trace",
      service: "api",
      severity: "error",
      message: "agent-zero operator copilot failed",
      agent_name: "agent-zero",
      event_type: "operator_copilot_failed",
      mode: "operator-copilot",
    });
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Envoyer un prompt avec routage */
agents.post("/send", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.send(body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Orchestrer plusieurs agents */
agents.post("/orchestrate", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.orchestrate(body);
    emitStructuredLog({
      source: "api-observation",
      service: "api",
      severity: result.results.some((row) => !!row.error) ? "warning" : "info",
      message: `orchestration completed with ${result.results.length} step(s)`,
      run_id: result.run_id,
      mode: result.mode,
      event_type: "orchestrate_completed",
      result_count: result.results.length,
    });
    return c.json(result);
  } catch (error) {
    emitStructuredLog({
      source: "api-observation",
      service: "api",
      severity: "error",
      message: "orchestration request failed",
      event_type: "orchestrate_failed",
    });
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Lister les providers disponibles */
agents.get("/providers", async (c) => {
  try {
    const result = await coreClient.listProviders();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Status detaille de tous les providers (cles, config) */
agents.get("/providers/status", async (c) => {
  try {
    const result = await coreClient.providersStatus();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Mettre a jour la cle d'un provider */
agents.put("/providers/:name/key", async (c) => {
  try {
    const name = c.req.param("name");
    if (!name || !SAFE_NAME_RE.test(name)) {
      return c.json({ error: "Invalid provider name" }, 400);
    }
    const { keys } = await c.req.json();
    const { response } = await providerMutationResult(
      c,
      name,
      `/providers/${encodeURIComponent(name)}`,
      {
        method: "PUT",
        body: JSON.stringify({ keys }),
      },
    );
    if (response.status < 400) {
      syncProviderEnvFromUpdate(keys || {});
    }
    return response;
  } catch (error) {
    if (error instanceof Error && !(error instanceof CoreApiError)) {
      return c.json({ error: error.message || "Ops Agent request failed" }, 503);
    }
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

agents.post("/providers/:name/clear", async (c) => {
  try {
    const name = c.req.param("name");
    if (!name || !SAFE_NAME_RE.test(name)) {
      return c.json({ error: "Invalid provider name" }, 400);
    }
    const body = (await c.req.json().catch(() => ({}))) as { fields?: string[] };
    const fields = Array.isArray(body.fields) ? body.fields.map((field) => String(field)) : undefined;
    const { response, payload } = await providerMutationResult(
      c,
      name,
      `/providers/${encodeURIComponent(name)}/clear`,
      {
        method: "POST",
        body: JSON.stringify(fields ? { fields } : {}),
      },
    );
    if (response.status < 400) {
      syncProviderEnvFromClear(payload?.cleared_env || fields || []);
    }
    return response;
  } catch (error) {
    if (error instanceof Error && !(error instanceof CoreApiError)) {
      return c.json({ error: error.message || "Ops Agent request failed" }, 503);
    }
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Recuperer le resume global de metriques */
agents.get("/metrics", async (c) => {
  try {
    const result = await coreClient.getMetrics();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Reset de toutes les metriques runtime */
agents.post("/metrics/reset", async (c) => {
  try {
    const result = await coreClient.resetMetrics();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Recuperer les metriques d'un provider */
agents.get("/metrics/:provider", async (c) => {
  try {
    const provider = c.req.param("provider");
    if (!provider || !SAFE_NAME_RE.test(provider)) {
      return c.json({ error: "Invalid provider name" }, 400);
    }
    const result = await coreClient.getProviderMetrics(provider);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Statistiques du cache de reponses */
agents.get("/cache/stats", async (c) => {
  try {
    const result = await coreClient.getCacheStats();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Reset cache */
agents.post("/cache/reset", async (c) => {
  try {
    const result = await coreClient.resetCache();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Statistiques du load balancer */
agents.get("/load-balancer/stats", async (c) => {
  try {
    const result = await coreClient.getLoadBalancerStats();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Reset load balancer */
agents.post("/load-balancer/reset", async (c) => {
  try {
    const result = await coreClient.resetLoadBalancer();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Statistiques fallback */
agents.get("/fallback/stats", async (c) => {
  try {
    const result = await coreClient.getFallbackStats();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Reset fallback */
agents.post("/fallback/reset", async (c) => {
  try {
    const result = await coreClient.resetFallback();
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Knowledge Scribe : executer puis pousser dans la knowledge base */
agents.post("/knowledge-scribe/run-and-push", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.knowledgeScribeRunAndPush(body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Recuperer les metriques d'un agent */
agents.get("/:name/metrics", async (c) => {
  try {
    const name = c.req.param("name");
    if (!name || !SAFE_NAME_RE.test(name)) {
      return c.json({ error: "Invalid agent name" }, 400);
    }
    const result = await coreClient.getAgentMetrics(name);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Detail agent */
agents.get("/:name", async (c) => {
  try {
    const name = c.req.param("name");
    if (!name || !SAFE_NAME_RE.test(name)) {
      return c.json({ error: "Invalid agent name" }, 400);
    }
    const result = await coreClient.getAgent(name);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Mettre a jour un agent */
agents.put("/:name", async (c) => {
  try {
    const name = c.req.param("name");
    if (!name || !SAFE_NAME_RE.test(name)) {
      return c.json({ error: "Invalid agent name" }, 400);
    }
    let raw: unknown;
    try {
      raw = await c.req.json();
    } catch {
      return c.json({ error: "Validation failed", details: [{ message: "Request body is not valid JSON" }] }, 400);
    }
    const parsed = AgentUpdateRequestSchema.safeParse(raw);
    if (!parsed.success) {
      return c.json({
        error: "Validation failed",
        details: parsed.error.issues.map((issue: { path: (string | number)[]; message: string; code: string }) => ({
          path: issue.path.join("."),
          message: issue.message,
          code: issue.code,
        })),
      }, 400);
    }
    const body = parsed.data;
    const result = await coreClient.updateAgent(name, body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

/** Supprimer un agent */
agents.delete("/:name", async (c) => {
  try {
    const name = c.req.param("name");
    if (!name || !SAFE_NAME_RE.test(name)) {
      return c.json({ error: "Invalid agent name" }, 400);
    }
    const result = await coreClient.deleteAgent(name);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { agents };
