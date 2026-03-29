import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "../Dashboard";

<<<<<<< Updated upstream
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

describe("Dashboard metrics lane", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderDashboard() {
=======
describe("Metrics", () => {
  function renderMetrics() {
>>>>>>> Stashed changes
    return render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );
  }

<<<<<<< Updated upstream
  it("shows loading panel while dashboard data is being fetched", () => {
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

  it("shows error notice when health fetch fails", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: false,
      error: "Timeout",
      refetch: mockRefetch,
      status: "error",
    });

    renderDashboard();
    expect(screen.getByText("Timeout")).toBeInTheDocument();
  });

  it("renders stable posture headline when health is nominal", () => {
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
        data: makeMonitorData(),
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "success",
      });

    renderDashboard();
    expect(screen.getByText("System matrix stable")).toBeInTheDocument();
  });

  it("renders degraded headline when gateway is under pressure", () => {
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
        data: makeMonitorData({
          gateway: { api: { ok: false, status: 503 }, core: false },
        }),
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "success",
      });

    renderDashboard();
    expect(screen.getByText("Gateway under pressure")).toBeInTheDocument();
  });

  it("shows action cards for operators", () => {
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
        data: makeMonitorData(),
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "success",
      });

    renderDashboard();
    expect(screen.getByText("Check Metrics")).toBeInTheDocument();
    expect(screen.getByText("Open Logs")).toBeInTheDocument();
  });

  it("shows refresh button and calls refetch on click", async () => {
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
        data: makeMonitorData(),
        loading: false,
        error: null,
        refetch: mockRefetch,
        status: "success",
      });

    renderDashboard();
    const btn = screen.getByRole("button", { name: /refresh status/i });
    await user.click(btn);
    expect(mockRefetch).toHaveBeenCalled();
=======
  it("renders the Metrics heading", () => {
    renderMetrics();
    expect(screen.getByText("Metrics")).toBeInTheDocument();
  });

  it("shows coming soon message", () => {
    renderMetrics();
    expect(screen.getByText("Coming soon")).toBeInTheDocument();
  });

  it("renders heading as h1", () => {
    renderMetrics();
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Metrics");
  });

  it("applies expected layout classes", () => {
    const { container } = renderMetrics();
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain("p-6");
  });

  it("renders subtitle with muted style", () => {
    renderMetrics();
    const subtitle = screen.getByText("Coming soon");
    expect(subtitle.className).toContain("text-gray-500");
  });

  it("renders heading with semibold font", () => {
    renderMetrics();
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading.className).toContain("font-semibold");
>>>>>>> Stashed changes
  });
});
