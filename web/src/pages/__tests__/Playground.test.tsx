import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Playground from "../Playground";

const mockRefetch = vi.fn();

const defaultProviderFetch = {
  data: { providers: ["openai", "mistral"] },
  loading: false,
  error: null,
  refetch: mockRefetch,
  status: "success" as const,
};

const defaultMonitorFetch = {
  data: null,
  loading: false,
  error: null,
  refetch: mockRefetch,
  status: "idle" as const,
};

vi.mock("../../hooks/useFetch", () => ({
  useFetch: vi.fn().mockImplementation((path: string) => {
    if (path === "/api/agents/providers") return defaultProviderFetch;
    return defaultMonitorFetch;
  }),
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
    send: vi.fn(),
  },
}));

import { useApi } from "../../hooks/useApi";
const mockedUseApi = vi.mocked(useApi);

describe("Playground", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseApi.mockReturnValue({
      execute: vi.fn(),
      data: null,
      loading: false,
      error: null,
      status: "idle",
    });
  });

  function renderPlayground() {
    return render(
      <MemoryRouter>
        <Playground />
      </MemoryRouter>,
    );
  }

  it("renders prompt lane headline and composer", () => {
    renderPlayground();
    expect(screen.getByText("Direct routing sandbox")).toBeInTheDocument();
    expect(screen.getByText("Prompt Composer")).toBeInTheDocument();
  });

  it("send button is disabled when prompt is empty", () => {
    renderPlayground();
    const sendBtn = screen.getByRole("button", { name: /send prompt/i });
    expect(sendBtn).toBeDisabled();
  });

  it("send button becomes enabled when prompt has text", async () => {
    const user = userEvent.setup();
    renderPlayground();

    const promptTextarea = screen.getByPlaceholderText(
      "Enter the prompt you want to route through Mascarade.",
    );
    await user.type(promptTextarea, "Hello world");

    const sendBtn = screen.getByRole("button", { name: /send prompt/i });
    expect(sendBtn).not.toBeDisabled();
  });

  it("shows response data after successful send", () => {
    mockedUseApi.mockReturnValue({
      execute: vi.fn(),
      data: {
        content: "Response from LLM",
        provider: "openai",
        model: "gpt-4",
        usage: { input_tokens: 10, output_tokens: 25 },
      },
      loading: false,
      error: null,
      status: "success",
    });

    renderPlayground();
    expect(screen.getByText("Response from LLM")).toBeInTheDocument();
    // "openai" appears in both the provider select option and the badge,
    // so check that at least one exists
    expect(screen.getAllByText("openai").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("gpt-4")).toBeInTheDocument();
    expect(screen.getByText("10 in / 25 out")).toBeInTheDocument();
  });

  it("shows error notice when dispatch fails", () => {
    mockedUseApi.mockReturnValue({
      execute: vi.fn(),
      data: null,
      loading: false,
      error: "Provider timeout",
      status: "error",
    });

    renderPlayground();
    expect(screen.getByText("Provider timeout")).toBeInTheDocument();
  });
});
