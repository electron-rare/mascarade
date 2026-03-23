import { Hono } from "hono";
import { handleCoreError } from "../../middleware/error.js";
import {
  type OpsLogEntry,
  type TimedJsonResult,
  timedJson,
  severityRank,
  sortLogs,
  coerceSeverity,
  labelsMatchRouting,
  traceToLogEntry,
  probeToLogEntry,
  lokiValueToOpsLogEntry,
  getNumberParam,
  opsAgentJson,
  proxySseResponse,
  parseSinceWindow,
  coreClient,
  LOKI_URL,
  OPS_AGENT_URL,
} from "./_shared.js";
import { collectMonitorSnapshot } from "./monitor.js";

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

// ── Routes ─────────────────────────────────────────────────────────────────

const logsRoutes = new Hono();

logsRoutes.get("/logs/recent", async (c) => {
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
          routing_policy: query.routing_policy,
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

logsRoutes.get("/logs/stream", async (c) => {
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

logsRoutes.get("/logs/query", async (c) => {
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
        routing_policy: query.routing_policy,
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

export { logsRoutes };
