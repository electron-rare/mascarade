import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Logs from "../Logs";

// Mock EventSource which is not available in jsdom
class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  readyState = 0;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  close() {
    this.readyState = 2;
  }
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() {
    return true;
  }
}
vi.stubGlobal("EventSource", MockEventSource);

const mockRefetch = vi.fn();

vi.mock("../../hooks/useFetch", () => ({
  useFetch: vi.fn(),
}));

vi.mock("../../hooks/useApi", () => ({
  useApi: vi.fn().mockReturnValue({
    execute: vi.fn(),
    data: null,
    loading: false,
    error: null,
  }),
}));

vi.mock("../../api/agents", () => ({
  agentsApi: {
    operatorCopilot: vi.fn().mockResolvedValue({ answer: "" }),
  },
}));

vi.mock("../../api/ops", () => ({
  opsApi: {
    logs: vi.fn().mockResolvedValue({ entries: [], count: 0 }),
    logStreamPath: vi.fn().mockReturnValue("/api/ops/logs/stream"),
    agentTraceStreamPath: vi.fn().mockReturnValue("/api/ops/agent-traces/stream"),
  },
}));

import { useFetch } from "../../hooks/useFetch";
const mockedUseFetch = vi.mocked(useFetch);

describe("Logs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderLogs() {
    return render(
      <MemoryRouter>
        <Logs />
      </MemoryRouter>,
    );
  }

  it("shows loading panel while logs are being fetched", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: mockRefetch,
      status: "loading",
    });

    renderLogs();
    expect(screen.getByText(/Opening.*logs/i)).toBeInTheDocument();
  });

  it("shows error notice when log fetch fails with no cached data", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: false,
      error: "Service unavailable",
      refetch: mockRefetch,
      status: "error",
    });

    renderLogs();
    expect(screen.getByText("Service unavailable")).toBeInTheDocument();
  });

  it("renders live observability headline when data arrives", () => {
    // The Logs component calls useFetch 5 times:
    // 1) summary, 2) sourceStatus, 3) liveSnapshot, 4) historyLogs, 5) runDetail
    // In live mode, liveSnapshot needs data for logsData to be non-null.
    // summary.data needs traces.active_runs for the posture chips.
    const summaryData = {
      alerts: [],
      traces: { active_runs: 0, recent_runs: [] },
      mcp: { total_servers: 0, ready_servers: 0, degraded_servers: [], servers: {}, aggregate_status: "pending" },
      cluster: null,
      sources: {},
      observability: {},
    };
    const logsPayload = {
      entries: [],
      count: 0,
      timestamp: "2026-03-26T10:00:00Z",
    };

    mockedUseFetch.mockImplementation((path: string | null) => {
      if (path?.includes("/api/ops/summary")) {
        return { data: summaryData, loading: false, error: null, refetch: mockRefetch, status: "success" as const };
      }
      if (path?.includes("/api/ops/sources")) {
        return { data: {}, loading: false, error: null, refetch: mockRefetch, status: "success" as const };
      }
      if (path?.includes("/api/ops/logs")) {
        return { data: logsPayload, loading: false, error: null, refetch: mockRefetch, status: "success" as const };
      }
      return { data: null, loading: false, error: null, refetch: mockRefetch, status: "idle" as const };
    });

    renderLogs();
    expect(screen.getByText("live observability")).toBeInTheDocument();
  });

  it("renders mode chip showing live", () => {
    const summaryData = {
      alerts: [],
      traces: { active_runs: 0, recent_runs: [] },
      mcp: { total_servers: 0, ready_servers: 0, degraded_servers: [], servers: {}, aggregate_status: "pending" },
      cluster: null,
      sources: {},
      observability: {},
    };
    const logsPayload = {
      entries: [],
      count: 0,
      timestamp: "2026-03-26T10:00:00Z",
    };

    mockedUseFetch.mockImplementation((path: string | null) => {
      if (path?.includes("/api/ops/summary")) {
        return { data: summaryData, loading: false, error: null, refetch: mockRefetch, status: "success" as const };
      }
      if (path?.includes("/api/ops/sources")) {
        return { data: {}, loading: false, error: null, refetch: mockRefetch, status: "success" as const };
      }
      if (path?.includes("/api/ops/logs")) {
        return { data: logsPayload, loading: false, error: null, refetch: mockRefetch, status: "success" as const };
      }
      return { data: null, loading: false, error: null, refetch: mockRefetch, status: "idle" as const };
    });

    renderLogs();
    expect(screen.getByText(/mode live/)).toBeInTheDocument();
  });
});
