import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Metrics from "../Metrics";

const mockRefetch = vi.fn();

vi.mock("../../hooks/useFetch", () => ({
  useFetch: vi.fn(),
}));

import { useFetch } from "../../hooks/useFetch";
const mockedUseFetch = vi.mocked(useFetch);

function makeMonitorData(overrides: Record<string, unknown> = {}) {
  return {
    timestamp: "2026-03-26T10:00:00Z",
    gateway: { api: { ok: true, status: 200 }, core: true },
    services: [
      { name: "ollama", ok: true, status: 200, latency_ms: 12, url: "http://ollama:11434", error: null },
      { name: "qdrant", ok: true, status: 200, latency_ms: 5, url: "http://qdrant:6333", error: null },
    ],
    ai: {
      ollama: { ok: true, models: 3, latency_ms: 12 },
      qdrant: { ok: true, collections: 2, latency_ms: 5 },
    },
    core_metrics: { ok: true, status: 200, data: { uptime: 3600 }, error: null },
    ...overrides,
  };
}

describe("Metrics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderMetrics() {
    return render(
      <MemoryRouter>
        <Metrics />
      </MemoryRouter>,
    );
  }

  it("shows loading panel while metrics are being fetched", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: mockRefetch,
      status: "loading",
    });

    renderMetrics();
    expect(screen.getByText("Syncing metrics")).toBeInTheDocument();
  });

  it("shows error notice when fetch fails", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: false,
      error: "Timeout",
      refetch: mockRefetch,
      status: "error",
    });

    renderMetrics();
    expect(screen.getByText("Timeout")).toBeInTheDocument();
  });

  it("renders stable posture headline when all services are ok", () => {
    mockedUseFetch.mockReturnValue({
      data: makeMonitorData(),
      loading: false,
      error: null,
      refetch: mockRefetch,
      status: "success",
    });

    renderMetrics();
    expect(screen.getByText("Runtime lanes stable")).toBeInTheDocument();
  });

  it("renders intervention headline when gateway is down", () => {
    mockedUseFetch.mockReturnValue({
      data: makeMonitorData({
        gateway: { api: { ok: false, status: 503 }, core: false },
      }),
      loading: false,
      error: null,
      refetch: mockRefetch,
      status: "success",
    });

    renderMetrics();
    expect(screen.getByText("Intervention lane open")).toBeInTheDocument();
  });

  it("renders services health table with service names", () => {
    mockedUseFetch.mockReturnValue({
      data: makeMonitorData(),
      loading: false,
      error: null,
      refetch: mockRefetch,
      status: "success",
    });

    renderMetrics();
    expect(screen.getByText("Services health table")).toBeInTheDocument();
    expect(screen.getByText("ollama")).toBeInTheDocument();
    expect(screen.getByText("qdrant")).toBeInTheDocument();
  });

  it("shows refresh button and calls refetch on click", async () => {
    const user = userEvent.setup();
    mockedUseFetch.mockReturnValue({
      data: makeMonitorData(),
      loading: false,
      error: null,
      refetch: mockRefetch,
      status: "success",
    });

    renderMetrics();
    const btn = screen.getByRole("button", { name: /refresh monitor/i });
    await user.click(btn);
    expect(mockRefetch).toHaveBeenCalled();
  });
});
