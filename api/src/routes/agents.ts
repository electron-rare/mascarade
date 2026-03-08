import { Hono, type Context } from "hono";
import { CoreApiError, coreClient } from "../client/core.js";
import { emitStructuredLog } from "../lib/otel.js";
import { handleCoreError } from "../middleware/error.js";

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
    return jsonWithStatus(c, json || { error: text || "Ops Agent request failed" }, upstream.status);
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
  return c.json(body);
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
    const body = await c.req.json();
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
    return await providerMutationResult(
      c,
      name,
      `/providers/${encodeURIComponent(name)}`,
      {
        method: "PUT",
        body: JSON.stringify({ keys }),
      },
    );
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
    return await providerMutationResult(
      c,
      name,
      `/providers/${encodeURIComponent(name)}/clear`,
      {
        method: "POST",
        body: JSON.stringify(fields ? { fields } : {}),
      },
    );
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

/** Notion Scribe : executer puis pousser dans Notion */
agents.post("/notion-scribe/run-and-push", async (c) => {
  try {
    const body = await c.req.json();
    const result = await coreClient.notionScribeRunAndPush(body);
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
    const body = await c.req.json();
    const result = await coreClient.updateAgent(name, body);
    return c.json(result);
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { agents };
