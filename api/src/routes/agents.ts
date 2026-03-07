import { Hono } from "hono";
import { coreClient } from "../client/core.js";
import { emitStructuredLog } from "../lib/otel.js";
import { handleCoreError } from "../middleware/error.js";

const agents = new Hono();
const SAFE_NAME_RE = /^[\w.-]+$/;

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
