import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Administration from "../Administration";

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

function mockControlFetches(options?: { servicesError?: string }) {
  mockedUseFetch.mockImplementation((path: string | null) => {
    if (path === "/api/admin/services") {
      return {
        data: options?.servicesError ? null : { services: [{ name: "mascarade-core", status: "running" }] },
        loading: false,
        error: options?.servicesError ?? null,
        refetch: mockRefetch,
        status: options?.servicesError ? "error" as const : "success" as const,
      };
    }
    if (path === "/api/admin/fleet/sync") {
      return { data: { nodes: [] }, loading: false, error: null, refetch: mockRefetch, status: "success" as const };
    }
    if (path === "/api/admin/training/status") {
      return { data: { running: false }, loading: false, error: null, refetch: mockRefetch, status: "success" as const };
    }
    if (path === "/api/users") {
      return { data: { users: [] }, loading: false, error: null, refetch: mockRefetch, status: "success" as const };
    }
    if (path === "/api/admin/audit") {
      return { data: { entries: [] }, loading: false, error: null, refetch: mockRefetch, status: "success" as const };
    }
    if (path === "/api/health") {
      return { data: { checks: { api: true } }, loading: false, error: null, refetch: mockRefetch, status: "success" as const };
    }
    return { data: null, loading: false, error: null, refetch: mockRefetch, status: "idle" as const };
  });
}

describe("Administration control lane", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderAdministration() {
    return render(
      <MemoryRouter>
        <Administration />
      </MemoryRouter>,
    );
  }

  it("renders the control surface cards", () => {
    mockControlFetches();

    renderAdministration();
    expect(screen.getByText("Service control")).toBeInTheDocument();
    expect(screen.getByText("Training control")).toBeInTheDocument();
    expect(screen.getByText("Logs & audit")).toBeInTheDocument();
  });

  it("surfaces the services API error note", () => {
    mockControlFetches({ servicesError: "Connection refused" });

    renderAdministration();
    expect(
      screen.getByText("Services endpoint: Connection refused. Affichage manifest statique."),
    ).toBeInTheDocument();
  });
});
