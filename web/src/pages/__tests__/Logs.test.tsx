import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Logs from "../Logs";

describe("Logs", () => {
  function renderLogs() {
    return render(
      <MemoryRouter>
        <Logs />
      </MemoryRouter>,
    );
  }

  it("renders the Logs heading", () => {
    renderLogs();
    expect(screen.getByText("Logs")).toBeInTheDocument();
  });

  it("shows coming soon message", () => {
    renderLogs();
    expect(screen.getByText("Coming soon")).toBeInTheDocument();
  });

  it("renders heading as h1", () => {
    renderLogs();
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Logs");
  });

  it("applies expected layout classes", () => {
    const { container } = renderLogs();
    const wrapper = container.firstElementChild as HTMLElement;
    expect(wrapper.className).toContain("p-6");
  });
});
