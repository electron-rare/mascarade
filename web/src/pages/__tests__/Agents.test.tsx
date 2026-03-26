import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Agents from "../Agents";

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
    status: "idle",
  }),
}));

vi.mock("../../api/agents", () => ({
  agentsApi: {
    create: vi.fn(),
    metrics: vi.fn().mockResolvedValue({ total_requests: 0, last_used: null }),
  },
}));

import { useFetch } from "../../hooks/useFetch";
const mockedUseFetch = vi.mocked(useFetch);

describe("Agents", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderAgents() {
    return render(
      <MemoryRouter>
        <Agents />
      </MemoryRouter>,
    );
  }

  it("shows loading panel while agents are being fetched", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: mockRefetch,
      status: "loading",
    });

    renderAgents();
    expect(screen.getByText("Loading registry")).toBeInTheDocument();
  });

  it("shows error notice on fetch failure", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: false,
      error: "Connection refused",
      refetch: mockRefetch,
      status: "error",
    });

    renderAgents();
    expect(screen.getByText("Connection refused")).toBeInTheDocument();
  });

  it("shows gateway auth error for session gateway errors", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: false,
      error: "Session gateway expiree",
      refetch: mockRefetch,
      status: "error",
    });

    renderAgents();
    expect(screen.getByText(/session gateway/i)).toBeInTheDocument();
  });

  it("renders agent list when data is available", () => {
    mockedUseFetch.mockReturnValue({
      data: {
        agents: [
          { name: "agent-zero", description: "Lead agent", builtin: true },
          { name: "code-reviewer", description: "Reviews code", builtin: false },
        ],
      },
      loading: false,
      error: null,
      refetch: mockRefetch,
      status: "success",
    });

    renderAgents();
    // agent-zero appears in both the featured card and the grid, so use getAllByText
    expect(screen.getAllByText("agent-zero").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("code-reviewer")).toBeInTheDocument();
    expect(screen.getByText("Reviews code")).toBeInTheDocument();
  });

  it("shows empty state when no agents exist", () => {
    mockedUseFetch.mockReturnValue({
      data: { agents: [] },
      loading: false,
      error: null,
      refetch: mockRefetch,
      status: "success",
    });

    renderAgents();
    expect(screen.getByText("No agents registered yet.")).toBeInTheDocument();
  });

  it("opens the create agent modal when clicking new agent", async () => {
    const user = userEvent.setup();
    mockedUseFetch.mockReturnValue({
      data: {
        agents: [
          { name: "agent-zero", description: "Lead agent", builtin: true },
        ],
      },
      loading: false,
      error: null,
      refetch: mockRefetch,
      status: "success",
    });

    renderAgents();
    const newBtn = screen.getByRole("button", { name: /new agent/i });
    await user.click(newBtn);

    expect(screen.getByText("Create Agent")).toBeInTheDocument();
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/system prompt/i)).toBeInTheDocument();
  });
});
