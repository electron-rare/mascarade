import { Hono } from "hono";
import { handleCoreError } from "../../middleware/error.js";
import {
  type MonitorSnapshot,
  type OpsLogEntry,
  timedProbe,
  timedJson,
  proxyAuthHeaders,
  industrialCockpitHeaders,
  isProxyPublic,
  sortLogs,
  traceToLogEntry,
  probeToLogEntry,
  opsAgentJson,
  lokiReady,
  coreClient,
  getCoreAuthHeaders,
  OLLAMA_BASE_URL,
  APPLE_LLM_ENABLED,
  APPLE_LLM_BASE_URL,
  EDGE_PROXY_BIND_HOST,
  EDGE_PROXY_SERVER_NAME,
  EDGE_PROXY_GRAFANA_SERVER_NAME,
  EDGE_PROXY_LANGFUSE_SERVER_NAME,
  EDGE_PROXY_OLLAMA_SERVER_NAME,
  EDGE_PROXY_PROMETHEUS_SERVER_NAME,
  EDGE_PROXY_MEM0_SERVER_NAME,
  EDGE_PROXY_FIRECRAWL_SERVER_NAME,
  EDGE_PROXY_SEARCH_SERVER_NAME,
  EDGE_PROXY_PAPERLESS_SERVER_NAME,
  EDGE_PROXY_KARAKEEP_SERVER_NAME,
  EDGE_PROXY_ZEROCLAW_SERVER_NAME,
  EDGE_PROXY_ZEROCLAW_DOCS_SERVER_NAME,
  EDGE_PROXY_LANGGRAPH_SERVER_NAME,
  EDGE_PROXY_INDUSTRIAL_SERVER_NAME,
  EDGE_PROXY_OPS_AUTH_USER,
  EDGE_PROXY_OPS_AUTH_PASSWORD,
  ZEROCLAW_GATEWAY_URL,
  ZEROCLAW_FOLLOW_URL,
  GRAFANA_PUBLIC_ORIGIN,
  LANGFUSE_PUBLIC_ORIGIN,
  FRAPPE_CRM_URL,
  frappeCrmAuthHeader,
} from "./_shared.js";
import { fetchOpsAgentMcpSummary } from "./mcp.js";

export async function collectMonitorSnapshot(): Promise<MonitorSnapshot> {
  const probes = await Promise.all([
    timedProbe("core", "http://core:8100/health"),
    timedProbe("grafana", "http://grafana:3000/api/health"),
    timedProbe("n8n", "http://n8n:5678/"),
    timedProbe("langfuse", "http://langfuse-web:3000/"),
    timedProbe("firecrawl", "http://firecrawl:3000/mcp", 1500, [400]),
    timedProbe("mem0", "http://mem0:8765/", 1500, [404, 405]),
    timedProbe("searxng", "http://mascarade-searxng:8080/", 1800, [200]),
    timedProbe("paperless", "http://mascarade-paperless:8000/api/", 1800, [200, 301, 302, 403]),
    timedProbe("karakeep", "http://mascarade-karakeep:3000/", 1800, [200, 301, 302, 307]),
    timedProbe("tempo", "http://tempo:3200/ready"),
    timedProbe("frappe-crm", `${FRAPPE_CRM_URL}/api/method/ping`, 2000),
    timedProbe("dify-web", "http://dify-web:3000/"),
    timedProbe("dify-api", "http://dify-api:5001/health"),
    timedProbe(
      "agent-factory-cockpit",
      "http://mascarade-agent-factory-cockpit:4173/api/session",
      1800,
      [200],
      industrialCockpitHeaders(),
    ),
    timedProbe("zeroclaw-gateway-live", `${ZEROCLAW_GATEWAY_URL}/health`, 1800, [200]),
    timedProbe("zeroclaw-follow-live", `${ZEROCLAW_FOLLOW_URL}/`, 1800, [200]),
    timedProbe("edge-proxy", "http://edge-proxy/healthz"),
    timedProbe(
      "grafana-proxy",
      "http://edge-proxy/login",
      1500,
      [200, 302, 401],
      proxyAuthHeaders(EDGE_PROXY_GRAFANA_SERVER_NAME),
    ),
    timedProbe(
      "langfuse-proxy",
      "http://edge-proxy/",
      1500,
      [200, 302, 401],
      proxyAuthHeaders(EDGE_PROXY_LANGFUSE_SERVER_NAME),
    ),
    timedProbe(
      "ollama-proxy",
      "http://edge-proxy/api/tags",
      1800,
      [200],
      proxyAuthHeaders(EDGE_PROXY_OLLAMA_SERVER_NAME),
    ),
    timedProbe(
      "prometheus-proxy",
      "http://edge-proxy/-/ready",
      1800,
      [200],
      proxyAuthHeaders(EDGE_PROXY_PROMETHEUS_SERVER_NAME),
    ),
    timedProbe(
      "mem0-proxy",
      "http://edge-proxy/docs",
      1800,
      [200, 301, 302],
      proxyAuthHeaders(EDGE_PROXY_MEM0_SERVER_NAME),
    ),
    timedProbe(
      "firecrawl-proxy",
      "http://edge-proxy/mcp",
      1800,
      [400],
      proxyAuthHeaders(EDGE_PROXY_FIRECRAWL_SERVER_NAME),
    ),
    timedProbe(
      "search-proxy",
      "http://edge-proxy/",
      1800,
      [200],
      proxyAuthHeaders(EDGE_PROXY_SEARCH_SERVER_NAME),
    ),
    timedProbe(
      "paperless-proxy",
      "http://edge-proxy/api/",
      1800,
      [200, 301, 302, 403],
      proxyAuthHeaders(EDGE_PROXY_PAPERLESS_SERVER_NAME),
    ),
    timedProbe(
      "karakeep-proxy",
      "http://edge-proxy/",
      1800,
      [200, 301, 302, 307],
      proxyAuthHeaders(EDGE_PROXY_KARAKEEP_SERVER_NAME),
    ),
    timedProbe(
      "industrial-proxy",
      "http://edge-proxy/",
      1800,
      [200],
      proxyAuthHeaders(EDGE_PROXY_INDUSTRIAL_SERVER_NAME),
    ),
    timedProbe(
      "zeroclaw-proxy",
      "http://edge-proxy/",
      1800,
      [200],
      proxyAuthHeaders(EDGE_PROXY_ZEROCLAW_SERVER_NAME),
    ),
    timedProbe(
      "zeroclaw-docs-proxy",
      "http://edge-proxy/",
      1800,
      [200],
      proxyAuthHeaders(EDGE_PROXY_ZEROCLAW_DOCS_SERVER_NAME),
    ),
    timedProbe(
      "langgraph-proxy",
      "http://edge-proxy/",
      1800,
      [200],
      proxyAuthHeaders(EDGE_PROXY_LANGGRAPH_SERVER_NAME),
    ),
  ]);

  const [ollama, qdrant, coreMetrics] = await Promise.all([
    timedJson(`${OLLAMA_BASE_URL}/api/tags`, 2200),
    timedJson("http://qdrant:6333/collections", 2200),
    timedJson("http://core:8100/metrics", 2200, getCoreAuthHeaders()),
  ]);
  const industrialPlatform = await coreClient.industrialMcpPlatform().catch(() => null);
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
  const tempoProbe = probes.find((probe) => probe.name === "tempo") ?? null;
  const edgeProxyProbe = probes.find((probe) => probe.name === "edge-proxy");
  const grafanaProxyProbe = probes.find((probe) => probe.name === "grafana-proxy");
  const langfuseProxyProbe = probes.find((probe) => probe.name === "langfuse-proxy");
  const ollamaProxyProbe = probes.find((probe) => probe.name === "ollama-proxy");
  const prometheusProxyProbe = probes.find((probe) => probe.name === "prometheus-proxy");
  const mem0ProxyProbe = probes.find((probe) => probe.name === "mem0-proxy");
  const firecrawlProxyProbe = probes.find((probe) => probe.name === "firecrawl-proxy");
  const searchProxyProbe = probes.find((probe) => probe.name === "search-proxy");
  const paperlessProxyProbe = probes.find((probe) => probe.name === "paperless-proxy");
  const karakeepProxyProbe = probes.find((probe) => probe.name === "karakeep-proxy");
  const industrialCockpitProbe = probes.find((probe) => probe.name === "agent-factory-cockpit");
  const industrialProxyProbe = probes.find((probe) => probe.name === "industrial-proxy");
  const zeroclawProxyProbe = probes.find((probe) => probe.name === "zeroclaw-proxy");
  const zeroclawDocsProxyProbe = probes.find((probe) => probe.name === "zeroclaw-docs-proxy");
  const langgraphProxyProbe = probes.find((probe) => probe.name === "langgraph-proxy");

  return {
    timestamp: new Date().toISOString(),
    gateway: {
      api: { ok: true, status: 200 },
      core: probes.find((p) => p.name === "core")?.ok ?? false,
    },
    observability: {
      traces_backend: "tempo",
      logs_backend: "loki",
      metrics_backend: "prometheus",
      tempo: tempoProbe,
      grafana_proxy_url: `${GRAFANA_PUBLIC_ORIGIN}/`,
      langfuse_proxy_url: `${LANGFUSE_PUBLIC_ORIGIN}/`,
    },
    public: {
      proxy_enabled: true,
      bind_host: EDGE_PROXY_BIND_HOST,
      public_bind: isProxyPublic(),
      server_name: EDGE_PROXY_SERVER_NAME,
      auth_configured: Boolean(EDGE_PROXY_OPS_AUTH_USER && EDGE_PROXY_OPS_AUTH_PASSWORD),
      surfaces: [
        {
          name: "edge-proxy",
          host: EDGE_PROXY_SERVER_NAME,
          url: `https://${EDGE_PROXY_SERVER_NAME}/`,
          protected: false,
          ok: edgeProxyProbe?.ok ?? false,
          status: edgeProxyProbe?.status ?? 0,
          latency_ms: edgeProxyProbe?.latency_ms ?? 0,
          note: "public entrypoint for app and ops gateway",
          ...(edgeProxyProbe?.error ? { error: edgeProxyProbe.error } : {}),
        },
        {
          name: "grafana",
          host: EDGE_PROXY_GRAFANA_SERVER_NAME,
          url: `${GRAFANA_PUBLIC_ORIGIN}/`,
          protected: true,
          ok: grafanaProxyProbe?.ok ?? false,
          status: grafanaProxyProbe?.status ?? 0,
          latency_ms: grafanaProxyProbe?.latency_ms ?? 0,
          note: "dashboards behind edge-proxy basic auth",
          ...(grafanaProxyProbe?.error ? { error: grafanaProxyProbe.error } : {}),
        },
        {
          name: "langfuse",
          host: EDGE_PROXY_LANGFUSE_SERVER_NAME,
          url: `${LANGFUSE_PUBLIC_ORIGIN}/`,
          protected: true,
          ok: langfuseProxyProbe?.ok ?? false,
          status: langfuseProxyProbe?.status ?? 0,
          latency_ms: langfuseProxyProbe?.latency_ms ?? 0,
          note: "llm traces behind edge-proxy basic auth",
          ...(langfuseProxyProbe?.error ? { error: langfuseProxyProbe.error } : {}),
        },
        {
          name: "prometheus",
          host: EDGE_PROXY_PROMETHEUS_SERVER_NAME,
          url: `https://${EDGE_PROXY_PROMETHEUS_SERVER_NAME}/`,
          protected: true,
          ok: prometheusProxyProbe?.ok ?? false,
          status: prometheusProxyProbe?.status ?? 0,
          latency_ms: prometheusProxyProbe?.latency_ms ?? 0,
          note: "raw metrics store behind edge-proxy basic auth",
          ...(prometheusProxyProbe?.error ? { error: prometheusProxyProbe.error } : {}),
        },
        {
          name: "ollama",
          host: EDGE_PROXY_OLLAMA_SERVER_NAME,
          url: `https://${EDGE_PROXY_OLLAMA_SERVER_NAME}/api/tags`,
          protected: true,
          ok: ollamaProxyProbe?.ok ?? false,
          status: ollamaProxyProbe?.status ?? 0,
          latency_ms: ollamaProxyProbe?.latency_ms ?? 0,
          note: "local model runtime behind edge-proxy basic auth",
          ...(ollamaProxyProbe?.error ? { error: ollamaProxyProbe.error } : {}),
        },
        {
          name: "mem0",
          host: EDGE_PROXY_MEM0_SERVER_NAME,
          url: `https://${EDGE_PROXY_MEM0_SERVER_NAME}/docs`,
          protected: true,
          ok: mem0ProxyProbe?.ok ?? false,
          status: mem0ProxyProbe?.status ?? 0,
          latency_ms: mem0ProxyProbe?.latency_ms ?? 0,
          note: "openmemory docs behind edge-proxy basic auth",
          ...(mem0ProxyProbe?.error ? { error: mem0ProxyProbe.error } : {}),
        },
        {
          name: "firecrawl",
          host: EDGE_PROXY_FIRECRAWL_SERVER_NAME,
          url: `https://${EDGE_PROXY_FIRECRAWL_SERVER_NAME}/mcp`,
          protected: true,
          ok: firecrawlProxyProbe?.ok ?? false,
          status: firecrawlProxyProbe?.status ?? 0,
          latency_ms: firecrawlProxyProbe?.latency_ms ?? 0,
          note: "streamable MCP endpoint behind edge-proxy basic auth",
          ...(firecrawlProxyProbe?.error ? { error: firecrawlProxyProbe.error } : {}),
        },
        {
          name: "search",
          host: EDGE_PROXY_SEARCH_SERVER_NAME,
          url: `https://${EDGE_PROXY_SEARCH_SERVER_NAME}/`,
          protected: true,
          ok: searchProxyProbe?.ok ?? false,
          status: searchProxyProbe?.status ?? 0,
          latency_ms: searchProxyProbe?.latency_ms ?? 0,
          note: "SearXNG search behind edge-proxy basic auth",
          ...(searchProxyProbe?.error ? { error: searchProxyProbe.error } : {}),
        },
        {
          name: "paperless",
          host: EDGE_PROXY_PAPERLESS_SERVER_NAME,
          url: `https://${EDGE_PROXY_PAPERLESS_SERVER_NAME}/`,
          protected: true,
          ok: paperlessProxyProbe?.ok ?? false,
          status: paperlessProxyProbe?.status ?? 0,
          latency_ms: paperlessProxyProbe?.latency_ms ?? 0,
          note: "Paperless-ngx documents behind edge-proxy basic auth",
          ...(paperlessProxyProbe?.error ? { error: paperlessProxyProbe.error } : {}),
        },
        {
          name: "karakeep",
          host: EDGE_PROXY_KARAKEEP_SERVER_NAME,
          url: `https://${EDGE_PROXY_KARAKEEP_SERVER_NAME}/`,
          protected: true,
          ok: karakeepProxyProbe?.ok ?? false,
          status: karakeepProxyProbe?.status ?? 0,
          latency_ms: karakeepProxyProbe?.latency_ms ?? 0,
          note: "Karakeep bookmarks behind edge-proxy basic auth",
          ...(karakeepProxyProbe?.error ? { error: karakeepProxyProbe.error } : {}),
        },
        {
          name: "industrial",
          host: EDGE_PROXY_INDUSTRIAL_SERVER_NAME,
          url: `https://${EDGE_PROXY_INDUSTRIAL_SERVER_NAME}/`,
          protected: true,
          ok: industrialProxyProbe?.ok ?? false,
          status: industrialProxyProbe?.status ?? 0,
          latency_ms: industrialProxyProbe?.latency_ms ?? 0,
          note: "industrial operator cockpit behind edge-proxy basic auth; live-ready MCP servers stay stdio/on-demand",
          ...(industrialProxyProbe?.error ? { error: industrialProxyProbe.error } : {}),
        },
        {
          name: "zeroclaw",
          host: EDGE_PROXY_ZEROCLAW_SERVER_NAME,
          url: `https://${EDGE_PROXY_ZEROCLAW_SERVER_NAME}/`,
          protected: true,
          ok: zeroclawProxyProbe?.ok ?? false,
          status: zeroclawProxyProbe?.status ?? 0,
          latency_ms: zeroclawProxyProbe?.latency_ms ?? 0,
          note: `ZeroClaw live follow UI behind edge-proxy basic auth; native runtime ${zeroclawProxyProbe?.ok ? "ready" : "stopped"}`,
          ...(zeroclawProxyProbe?.error ? { error: zeroclawProxyProbe.error } : {}),
        },
        {
          name: "zeroclaw-docs",
          host: EDGE_PROXY_ZEROCLAW_DOCS_SERVER_NAME,
          url: `https://${EDGE_PROXY_ZEROCLAW_DOCS_SERVER_NAME}/`,
          protected: true,
          ok: zeroclawDocsProxyProbe?.ok ?? false,
          status: zeroclawDocsProxyProbe?.status ?? 0,
          latency_ms: zeroclawDocsProxyProbe?.latency_ms ?? 0,
          note: "ZeroClaw static runbook behind edge-proxy basic auth; available even when runtime is stopped",
          ...(zeroclawDocsProxyProbe?.error ? { error: zeroclawDocsProxyProbe.error } : {}),
        },
        {
          name: "langgraph",
          host: EDGE_PROXY_LANGGRAPH_SERVER_NAME,
          url: `https://${EDGE_PROXY_LANGGRAPH_SERVER_NAME}/`,
          protected: true,
          ok: langgraphProxyProbe?.ok ?? false,
          status: langgraphProxyProbe?.status ?? 0,
          latency_ms: langgraphProxyProbe?.latency_ms ?? 0,
          note: "LangGraph operator overlay runbook behind edge-proxy basic auth; no always-on runtime required",
          ...(langgraphProxyProbe?.error ? { error: langgraphProxyProbe.error } : {}),
        },
      ],
    },
    industrial: {
      ui: industrialProxyProbe ? {
        host: EDGE_PROXY_INDUSTRIAL_SERVER_NAME,
        url: `https://${EDGE_PROXY_INDUSTRIAL_SERVER_NAME}/`,
        ok: industrialProxyProbe.ok,
        status: industrialProxyProbe.status,
        latency_ms: industrialProxyProbe.latency_ms,
        note: "industrial cockpit UI proxied with operator auth; runtime MCP stdio discovery remains on-demand",
        ...(industrialProxyProbe.error ? { error: industrialProxyProbe.error } : {}),
      } : null,
      summary: {
        server_count: Number(industrialPlatform?.summary?.server_count ?? 0),
        runtime_ok_count: Number(industrialPlatform?.summary?.runtime_ok_count ?? 0),
        runtime_error_count: Number(industrialPlatform?.summary?.runtime_error_count ?? 0),
        topology_valid: Boolean(industrialPlatform?.summary?.topology_valid ?? false),
        vendor_contract_ready_count: Number(industrialPlatform?.summary?.vendor_contract_ready_count ?? 0),
        vendor_contract_blocked_count: Number(industrialPlatform?.summary?.vendor_contract_blocked_count ?? 0),
        cockpit_service_ok: industrialCockpitProbe?.ok ?? false,
        cockpit_proxy_ok: industrialProxyProbe?.ok ?? false,
      },
      servers: Array.isArray(industrialPlatform?.servers)
        ? industrialPlatform.servers.map((server: Record<string, unknown>) => ({
            key: String(server.key || ""),
            label: String(server.label || server.key || ""),
            description: String(server.description || ""),
            ok: Boolean(server.ok ?? server.runtime_ok ?? false),
            runtime_ok: Boolean(server.runtime_ok ?? server.ok ?? false),
            protocol_version: String(server.protocol_version || ""),
            tool_count: Number(server.tool_count || 0),
            resource_count: Number(server.resource_count || 0),
            prompt_count: Number(server.prompt_count || 0),
            ...(server.health && typeof server.health === "object"
              ? { health: server.health as Record<string, unknown> }
              : {}),
            ...(server.contract && typeof server.contract === "object"
              ? { contract: server.contract as Record<string, unknown> }
              : {}),
            ...(server.error ? { error: String(server.error) } : {}),
          }))
        : [],
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

// ── Routes ─────────────────────────────────────────────────────────────────

const monitorRoutes = new Hono();

monitorRoutes.get("/monitor", async (c) => c.json(await collectMonitorSnapshot()));

monitorRoutes.get("/sources", async (c) =>
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
        gpu: {
          available: !!opsAgentSources.json?.gpu?.available,
          kind: opsAgentSources.json?.gpu?.kind || "ops-agent",
          ...(Array.isArray(opsAgentSources.json?.gpu?.gpus) ? { gpus: opsAgentSources.json.gpu.gpus } : {}),
          ...(opsAgentSources.json?.gpu?.error ? { error: opsAgentSources.json.gpu.error } : {}),
        },
        loki_history: { available: loki, kind: "loki" },
        tempo_traces: {
          available: (process.env.OTEL_ENABLED || "").toLowerCase() === "true",
          kind: "tempo",
        },
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

monitorRoutes.get("/summary", async (c) => {
  try {
    const [monitor, traces, opsAgent, mcp, loki, clusterIdentity, clusterPeers, providerHealth] = await Promise.all([
      collectMonitorSnapshot(),
      coreClient.recentAgentTraces({ limit: 60 }),
      opsAgentJson("/summary", 5000),
      fetchOpsAgentMcpSummary(false),
      lokiReady(),
      coreClient.clusterIdentity().catch(() => null),
      coreClient.clusterPeers().catch(() => null),
      coreClient.providerHealth().catch(() => ({})),
    ]);

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
        gpu: !!opsAgent.json?.sources?.gpu?.available,
        loki_history: loki,
        tempo_traces: monitor.observability.tempo?.ok ?? false,
        otel: (process.env.OTEL_ENABLED || "").toLowerCase() === "true",
        agentsight: !!opsAgent.json?.sources?.agentsight?.available,
      },
      observability: monitor.observability,
      public: monitor.public,
      industrial: monitor.industrial,
      cluster: {
        enabled: !!clusterIdentity?.cluster_enabled,
        node_id: clusterIdentity?.node_id || null,
        role: clusterIdentity?.role || null,
        peers_total: clusterPeers?.peers?.length || 0,
        peers_ok: clusterPeers?.peers?.filter((peer) => peer.ok).length || 0,
      },
      provider_health: providerHealth,
      gpu: opsAgent.json?.sources?.gpu ?? null,
      mcp,
      ops_agent: opsAgent.json ?? null,
    });
  } catch (error) {
    const { status, body } = handleCoreError(error);
    return c.json(body, status);
  }
});

export { monitorRoutes };
