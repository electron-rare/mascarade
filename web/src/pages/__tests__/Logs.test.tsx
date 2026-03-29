import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Pipeline from "../Pipeline";

const mockRefetch = vi.fn();

vi.mock("../../hooks/useFetch", () => ({
  useFetch: vi.fn(),
}));

import { useFetch } from "../../hooks/useFetch";
const mockedUseFetch = vi.mocked(useFetch);

describe("Pipeline page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderPipeline() {
    return render(
      <MemoryRouter>
        <Pipeline />
      </MemoryRouter>,
    );
  }

  it("shows loading panel while pipeline status is being fetched", () => {
    mockedUseFetch.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: mockRefetch,
      status: "loading",
    });

    renderPipeline();
    expect(screen.getByText("Loading pipeline")).toBeInTheDocument();
  });

  it("shows pipeline refresh notice when status fetch reports an error", () => {
    mockedUseFetch.mockReturnValue({
      data: { steps: [], running: false },
      loading: false,
      error: "Service unavailable",
      refetch: mockRefetch,
      status: "error",
    });

    renderPipeline();
    expect(screen.getByText("Refresh failed: Service unavailable")).toBeInTheDocument();
  });

  it("renders the training pipeline headline and action button", () => {
    mockedUseFetch.mockImplementation((path: string | null) => {
      if (path === "/api/pipeline/status") {
        return {
          data: {
            steps: [{ id: "clone", label: "Clone Sources", description: "Clone Tier 1 repos", endpoint: "/api/pipeline/clone", buttonLabel: "Run Clone", status: "idle", progress_pct: 0, duration_s: null, last_run: null, logs: [] }],
            running: false,
          },
          loading: false,
          error: null,
          refetch: mockRefetch,
          status: "success" as const,
        };
      }
      return { data: null, loading: false, error: null, refetch: mockRefetch, status: "idle" as const };
    });

    renderPipeline();
    expect(screen.getByText("Training Pipeline")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run full pipeline/i })).toBeInTheDocument();
  });
});
