import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import OpsHub from "../OpsHub";

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

vi.mock("../../lib/dify", () => ({
  getDifyOrigin: () => "http://localhost:3000",
  getDifyHealthUrl: () => "http://localhost:3000/health",
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
      ollama: { ok: true, models: 3, model_names: ["llama3"], latency_ms: 12 },
      qdrant: { ok: true, collections: 2, latency_ms: 5 },
    },
    core_metrics: { ok: true, status: 200, data: {}, error: null },
    observability: { tempo: { ok: false } },
    public: { surfaces: [], public_bind: null, auth_configured: false },
    industrial: { servers: [], summary: { runtime_ok_count: 0, server_count: 0 } },
    ...overrides,
  };
}

function useFetchSuccess(data: unknown) {
  return {
    data,
    loading: false,
    error: null,
    refetch: mockRefetch,
    status: "success" as const,
  };
}

function useFetchIdle() {
  return {
    data: null,
    loading: false,
    error: null,
    refetch: mockRefetch,
    status: "idle" as const,
  };
}

describe("OpsHub", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderOpsHub() {
    return render(
      <MemoryRouter>
        <OpsHub />
      </MemoryRouter>,
    );
  }

  it("shows loading panel while data is being fetched", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: mockRefetch,
      status: "loading",
    });

    renderOpsHub();
    expect(screen.getByText("Opening ops hub")).toBeInTheDocument();
  });

  it("shows error notice when fetch fails", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: false,
      error: "Connection refused",
      refetch: mockRefetch,
      status: "error",
    });

    renderOpsHub();
    expect(screen.getByText("Connection refused")).toBeInTheDocument();
  });

  it("renders ops hub headline when data loads", () => {
    // OpsHub calls useFetch 4 times: monitor, summary, sourceStatus, qdrantCollections
    mockedUseFetch
      .mockReturnValueOnce(useFetchSuccess(makeMonitorData()))
      .mockReturnValueOnce(useFetchIdle())
      .mockReturnValueOnce(useFetchIdle())
      .mockReturnValueOnce(useFetchIdle());

    renderOpsHub();
    expect(screen.getByText("ops hub")).toBeInTheDocument();
    expect(screen.getByText("Runtime entrypoint and local service lane")).toBeInTheDocument();
  });

  it("renders posture and gateway status chips", () => {
    mockedUseFetch
      .mockReturnValueOnce(useFetchSuccess(makeMonitorData()))
      .mockReturnValueOnce(useFetchIdle())
      .mockReturnValueOnce(useFetchIdle())
      .mockReturnValueOnce(useFetchIdle());

    renderOpsHub();
    expect(screen.getByText(/posture nominal/)).toBeInTheDocument();
    expect(screen.getByText(/api online/)).toBeInTheDocument();
    expect(screen.getByText(/core online/)).toBeInTheDocument();
  });

  it("shows refresh button and triggers refetch on click", async () => {
    const user = userEvent.setup();
    mockedUseFetch
      .mockReturnValueOnce(useFetchSuccess(makeMonitorData()))
      .mockReturnValueOnce(useFetchIdle())
      .mockReturnValueOnce(useFetchIdle())
      .mockReturnValueOnce(useFetchIdle());

    renderOpsHub();
    const refreshBtn = screen.getByRole("button", { name: /refresh hub/i });
    await user.click(refreshBtn);
    expect(mockRefetch).toHaveBeenCalled();
  });
});
