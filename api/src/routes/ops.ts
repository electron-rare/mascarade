import { Hono } from "hono";
import { getCoreAuthHeaders } from "../client/core.js";

type ProbeResult = {
  name: string;
  url: string;
  ok: boolean;
  status: number;
  latency_ms: number;
  error?: string;
};

async function timedJson(
  url: string,
  timeoutMs: number = 1800,
  headers?: Record<string, string>,
): Promise<{ ok: boolean; status: number; latencyMs: number; json?: any; error?: string }> {
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

const ops = new Hono();

ops.get("/monitor", async (c) => {
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
    timedJson("http://ollama:11434/api/tags", 2200),
    timedJson("http://qdrant:6333/collections", 2200),
    timedJson("http://core:8100/metrics", 2200, getCoreAuthHeaders()),
  ]);

  const ollamaModels = Array.isArray(ollama.json?.models) ? ollama.json.models.length : 0;
  const qdrantCollections = Array.isArray(qdrant.json?.result?.collections)
    ? qdrant.json.result.collections.length
    : 0;

  return c.json({
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
        error: ollama.error,
      },
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
  });
});

export { ops };
