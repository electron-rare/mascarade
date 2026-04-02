import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Documents from "../Documents";

const mockGet = vi.fn();

vi.mock("../../api/client", () => ({
  get: (...args: unknown[]) => mockGet(...args),
}));

describe("Documents", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderPage() {
    return render(
      <MemoryRouter>
        <Documents />
      </MemoryRouter>,
    );
  }

  it("resolves a business object before opening it", async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    mockGet.mockResolvedValue({
      object: "invoice",
      object_id: "123",
      nextcloud_path: "/clients/CLI-0042/factures/FA-2026-0015.pdf",
      drive_url: "https://drive.saillant.cc/?open=x",
      open_url: "https://drive.saillant.cc/?open=x",
      download_url: null,
      mode: "browse",
      target: "drive",
      editor: "drive",
    });

    renderPage();

    await user.click(screen.getByRole("button", { name: /ouvrir via mascarade/i }));

    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(String(mockGet.mock.calls[0][0])).toContain("/files/by-business-object?");
    expect(openSpy).toHaveBeenCalledWith("https://drive.saillant.cc/?open=x", "_blank", "noopener,noreferrer");
  });

  it("shows the resolved editor metadata", async () => {
    const user = userEvent.setup();

    mockGet.mockResolvedValue({
      object: "proposal",
      object_id: "77",
      nextcloud_path: "/clients/CLI-0042/devis/PR-2026-0042.odt",
      drive_url: "https://drive.saillant.cc/?open=proposal",
      open_url: "https://docs.saillant.cc/?open=proposal",
      download_url: null,
      mode: "edit",
      target: "docs",
      editor: "docs",
    });

    renderPage();

    await user.click(screen.getByRole("button", { name: /^resoudre$/i }));

    expect(await screen.findByText(/mode edit · editor docs/i)).toBeInTheDocument();
    expect(screen.getByText("/clients/CLI-0042/devis/PR-2026-0042.odt")).toBeInTheDocument();
  });
});
