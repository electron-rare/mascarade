import { describe, expect, it } from "vitest";
import { decodeLokiLine, lokiValueToOpsLogEntry } from "./ops.js";

describe("decodeLokiLine", () => {
  it("unwraps docker json envelopes before parsing structured logs", () => {
    const decoded = decodeLokiLine(
      JSON.stringify({
        log: JSON.stringify({
          source: "agent-trace",
          service: "core",
          severity: "warning",
          message: "agent-zero -> planner handoff",
          run_id: "run-123",
          agent_name: "agent-zero",
          event_type: "handoff",
        }) + "\n",
        stream: "stdout",
        time: "2026-03-07T18:12:14.123456789Z",
      }),
    );

    expect(decoded.envelopeTs).toBe("2026-03-07T18:12:14.123456789Z");
    expect(decoded.structured).toMatchObject({
      source: "agent-trace",
      service: "core",
      run_id: "run-123",
    });
  });
});

describe("lokiValueToOpsLogEntry", () => {
  it("builds a structured agent-trace entry from docker-wrapped json logs", () => {
    const entry = lokiValueToOpsLogEntry({
      rawTimestampNs: String(Date.parse("2026-03-07T18:12:14.999Z") * 1_000_000),
      rawLine: JSON.stringify({
        log: JSON.stringify({
          id: "trace-1",
          source: "agent-trace",
          service: "core",
          severity: "warning",
          message: "agent-zero -> planner handoff",
          run_id: "run-123",
          agent_name: "agent-zero",
          from_agent: "agent-zero",
          to_agent: "planner",
          event_type: "handoff",
        }) + "\n",
        stream: "stdout",
        time: "2026-03-07T18:12:14.123456789Z",
      }),
      labels: { job: "docker" },
    });

    expect(entry).toEqual({
      id: "trace-1",
      ts: "2026-03-07T18:12:14.123Z",
      source: "agent-trace",
      service: "core",
      severity: "warning",
      message: "agent-zero -> planner handoff",
      run_id: "run-123",
      agent_name: "agent-zero",
      from_agent: "agent-zero",
      to_agent: "planner",
      event_type: "handoff",
      labels: { job: "docker" },
    });
  });

  it("falls back to service log inference for plain docker lines", () => {
    const entry = lokiValueToOpsLogEntry({
      rawTimestampNs: String(Date.parse("2026-03-07T19:00:00.000Z") * 1_000_000),
      rawLine: "fatal: backend failed to bind",
      labels: {
        job: "docker",
        service: "api",
      },
    });

    expect(entry).toMatchObject({
      source: "service",
      service: "api",
      severity: "critical",
      message: "fatal: backend failed to bind",
    });
  });

  it("maps journald lines to machine source when they are not structured", () => {
    const entry = lokiValueToOpsLogEntry({
      rawTimestampNs: String(Date.parse("2026-03-07T19:10:00.000Z") * 1_000_000),
      rawLine: "kernel: warning thermal limit reached",
      labels: {
        job: "systemd-journal",
        unit: "kernel",
      },
    });

    expect(entry).toMatchObject({
      source: "machine",
      service: "kernel",
      severity: "warning",
    });
  });
});
