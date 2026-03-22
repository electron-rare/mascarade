type Severity = "debug" | "info" | "warn" | "warning" | "error" | "critical";

function severityNumber(severity: Severity): number {
  switch (severity) {
    case "debug":
      return 5;
    case "info":
      return 9;
    case "warning":
      return 13;
    case "error":
      return 17;
    case "critical":
      return 21;
    default:
      return 9;
  }
}

function otelEnabled(): boolean {
  return (process.env.OTEL_ENABLED || "").toLowerCase() === "true";
}

function collectorEndpoint(): string {
  return (process.env.OTEL_COLLECTOR_HTTP_ENDPOINT || "http://otel-collector:4318").replace(/\/+$/, "");
}

export function emitStructuredLog(entry: {
  source?: string;
  service: string;
  severity: Severity;
  message: string;
  run_id?: string;
  agent_name?: string;
  event_type?: string;
  mode?: string;
  result_count?: number;
  [key: string]: unknown;
}) {
  const logEntry = { source: "api", ...entry };
  console.log(JSON.stringify(logEntry));

  if (!otelEnabled()) {
    return;
  }

  const payload = {
    resourceLogs: [
      {
        resource: {
          attributes: [
            {
              key: "service.name",
              value: { stringValue: logEntry.service },
            },
          ],
        },
        scopeLogs: [
          {
            scope: { name: "mascarade-api" },
            logRecords: [
              {
                timeUnixNano: `${Date.now()}000000`,
                severityText: logEntry.severity.toUpperCase(),
                severityNumber: severityNumber(logEntry.severity),
                body: { stringValue: logEntry.message },
                attributes: Object.entries(logEntry)
                  .filter(([key, value]) =>
                    key !== "message" &&
                    key !== "severity" &&
                    key !== "service" &&
                    value !== undefined &&
                    value !== null
                  )
                  .map(([key, value]) => ({
                    key,
                    value: { stringValue: String(value) },
                  })),
              },
            ],
          },
        ],
      },
    ],
  };

  void fetch(`${collectorEndpoint()}/v1/logs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(1200),
  }).catch(() => undefined);
}
