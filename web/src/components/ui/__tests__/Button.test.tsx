import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import Button from "../Button";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument();
  });

  it("calls onClick handler when clicked", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click</Button>);

    await user.click(screen.getByRole("button", { name: "Click" }));
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it("is disabled and shows spinner when loading", () => {
    render(<Button loading>Save</Button>);
    const button = screen.getByRole("button", { name: /Save/ });

    expect(button).toBeDisabled();
    expect(button.textContent).toContain("⟳");
  });

  it("does not fire onClick when loading", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<Button loading onClick={handleClick}>Save</Button>);

    await user.click(screen.getByRole("button", { name: /Save/ }));
    expect(handleClick).not.toHaveBeenCalled();
  });

  it("is disabled when disabled prop is true", () => {
    render(<Button disabled>Nope</Button>);
    expect(screen.getByRole("button", { name: "Nope" })).toBeDisabled();
  });

  it("does not fire onClick when disabled", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(<Button disabled onClick={handleClick}>Nope</Button>);

    await user.click(screen.getByRole("button", { name: "Nope" }));
    expect(handleClick).not.toHaveBeenCalled();
  });

  it("applies the primary variant classes by default", () => {
    render(<Button>Primary</Button>);
    const button = screen.getByRole("button", { name: "Primary" });
    expect(button.className).toContain("bg-accent");
  });

  it("applies the danger variant classes", () => {
    render(<Button variant="danger">Delete</Button>);
    const button = screen.getByRole("button", { name: "Delete" });
    expect(button.className).toContain("bg-error");
  });
});
