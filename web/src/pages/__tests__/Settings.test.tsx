import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Administration from "../Administration";

vi.mock("../../api/client", () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  isPersisted: vi.fn().mockReturnValue(false),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : String(error)),
}));

vi.mock("../../auth/AuthContext", () => ({
  useAuth: vi.fn().mockReturnValue({
    login: vi.fn(),
    logout: vi.fn(),
    token: null,
    isAuthenticated: false,
  }),
}));

import { get } from "../../api/client";
const mockedGet = vi.mocked(get);

describe("Settings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders provider administration section after loading", async () => {
    mockedGet.mockImplementation((path: string) => {
      if (path.includes("providers/status")) {
        return Promise.resolve({
          providers: [
            {
              name: "openai",
              label: "OpenAI",
              configured: true,
              active: true,
              fields: [],
              default_model: "gpt-4",
              models: ["gpt-4"],
            },
          ],
        });
      }
      if (path.includes("runtime-secrets")) {
        return Promise.resolve({ groups: [] });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter>
        <Administration />
      </MemoryRouter>,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: /settings/i }));
    await waitFor(() => {
      expect(screen.getByText("provider administration")).toBeInTheDocument();
    });
  });

  it("shows active and inactive provider counts", async () => {
    mockedGet.mockImplementation((path: string) => {
      if (path.includes("providers/status")) {
        return Promise.resolve({
          providers: [
            { name: "openai", label: "OpenAI", configured: true, active: true, fields: [], default_model: null, models: [] },
            { name: "mistral", label: "Mistral", configured: false, active: false, fields: [], default_model: null, models: [] },
          ],
        });
      }
      if (path.includes("runtime-secrets")) {
        return Promise.resolve({ groups: [] });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter>
        <Administration />
      </MemoryRouter>,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: /settings/i }));
    await waitFor(() => {
      expect(screen.getByText("1 actif")).toBeInTheDocument();
      expect(screen.getByText("1 non configure")).toBeInTheDocument();
    });
  });

  it("renders runtime security section", async () => {
    mockedGet.mockImplementation((path: string) => {
      if (path.includes("providers/status")) {
        return Promise.resolve({ providers: [] });
      }
      if (path.includes("runtime-secrets")) {
        return Promise.resolve({
          groups: [
            {
              name: "api-key",
              label: "API Key",
              description: "Main API key",
              configured: true,
              configured_count: 1,
              field_count: 1,
              generate_supported: false,
              restart_services: [],
              fields: [],
              criticality: "required-security",
            },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter>
        <Administration />
      </MemoryRouter>,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: /settings/i }));
    await waitFor(() => {
      expect(screen.getByText("runtime security + integrations")).toBeInTheDocument();
    });
  });

  it("renders secret matrix section", async () => {
    mockedGet.mockImplementation((path: string) => {
      if (path.includes("providers/status")) {
        return Promise.resolve({ providers: [] });
      }
      if (path.includes("runtime-secrets")) {
        return Promise.resolve({ groups: [] });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter>
        <Administration />
      </MemoryRouter>,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: /settings/i }));
    await waitFor(() => {
      expect(screen.getByText("provider administration")).toBeInTheDocument();
      expect(screen.getByText("runtime security + integrations")).toBeInTheDocument();
    });
  });

  it("handles fetch error gracefully", async () => {
    mockedGet.mockRejectedValue(new Error("Network failure"));

    render(
      <MemoryRouter>
        <Administration />
      </MemoryRouter>,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: /settings/i }));
    await waitFor(() => {
      expect(screen.getByText("Network failure")).toBeInTheDocument();
    });
  });
});
