type Severity = "debug" | "info" | "warning" | "error" | "critical";

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
  source: string;
  service: string;
  severity: Severity;
  message: string;
  run_id?: string;
  agent_name?: string;
  event_type?: string;
  mode?: string;
  result_count?: number;
}) {
  console.log(JSON.stringify(entry));

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
              value: { stringValue: entry.service },
            },
          ],
        },
        scopeLogs: [
          {
            scope: { name: "mascarade-api" },
            logRecords: [
              {
                timeUnixNano: `${Date.now()}000000`,
                severityText: entry.severity.toUpperCase(),
                severityNumber: severityNumber(entry.severity),
                body: { stringValue: entry.message },
                attributes: Object.entries(entry)
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
