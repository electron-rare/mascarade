import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "../Dashboard";

// Mock useFetch to control data flow
const mockRefetch = vi.fn();
vi.mock("../../hooks/useFetch", () => ({
  useFetch: vi.fn(),
}));

import { useFetch } from "../../hooks/useFetch";
const mockedUseFetch = vi.mocked(useFetch);

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderDashboard() {
    return render(
      <MemoryRouter>
        <Dashboard />
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

    renderDashboard();
    expect(screen.getByText("Syncing dashboard")).toBeInTheDocument();
  });

  it("shows error notice when fetch fails with no cached data", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: false,
      error: "Network error",
      refetch: mockRefetch,
      status: "error",
    });

    renderDashboard();
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("renders runtime posture headline when system is ok", () => {
    // First call: /health, second call: /api/ops/monitor
    mockedUseFetch
      .mockReturnValueOnce({
        data: {
          status: "ok",
          core: { status: "ok", providers: ["openai", "mistral"], agents: 5 },
        },
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "success",
      })
      .mockReturnValueOnce({
        data: null,
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "idle",
      });

    renderDashboard();
    expect(screen.getByText("System matrix stable")).toBeInTheDocument();
    expect(screen.getByText(/2 provider\(s\) actifs et 5 agent\(s\)/)).toBeInTheDocument();
  });

  it("renders degraded headline when system is not ok", () => {
    mockedUseFetch
      .mockReturnValueOnce({
        data: {
          status: "degraded",
          core: { status: "error", providers: [], agents: 0 },
        },
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "success",
      })
      .mockReturnValueOnce({
        data: null,
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "idle",
      });

    renderDashboard();
    expect(screen.getByText("Gateway under pressure")).toBeInTheDocument();
  });

  it("renders action cards with correct links", () => {
    mockedUseFetch
      .mockReturnValueOnce({
        data: {
          status: "ok",
          core: { status: "ok", providers: ["openai"], agents: 3 },
        },
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "success",
      })
      .mockReturnValueOnce({
        data: null,
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "idle",
      });

    renderDashboard();
    expect(screen.getByText("Open Playground")).toBeInTheDocument();
    expect(screen.getByText("Inspect Agents")).toBeInTheDocument();
    expect(screen.getByText("Check Metrics")).toBeInTheDocument();
    expect(screen.getByText("Open Logs")).toBeInTheDocument();
  });

  it("shows refresh status button and calls refetch on click", async () => {
    const user = userEvent.setup();
    mockedUseFetch
      .mockReturnValueOnce({
        data: {
          status: "ok",
          core: { status: "ok", providers: ["openai"], agents: 1 },
        },
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "success",
      })
      .mockReturnValueOnce({
        data: null,
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "idle",
      });

    renderDashboard();
    const refreshBtn = screen.getByRole("button", { name: /refresh status/i });
    await user.click(refreshBtn);
    expect(mockRefetch).toHaveBeenCalled();
  });
});
