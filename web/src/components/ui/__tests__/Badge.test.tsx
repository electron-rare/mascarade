import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import Badge from "../Badge";

describe("Badge", () => {
  it("renders text content", () => {
    render(<Badge>active</Badge>);
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("applies muted variant classes by default", () => {
    render(<Badge>default</Badge>);
    const badge = screen.getByText("default");
    expect(badge.className).toContain("bg-black");
    expect(badge.className).toContain("text-muted");
  });

  it("applies accent color classes", () => {
    render(<Badge color="accent">running</Badge>);
    const badge = screen.getByText("running");
    expect(badge.className).toContain("bg-accent");
    expect(badge.className).toContain("text-accent");
  });

  it("applies error color classes", () => {
    render(<Badge color="error">failed</Badge>);
    const badge = screen.getByText("failed");
    expect(badge.className).toContain("bg-error");
    expect(badge.className).toContain("text-error");
  });

  it("applies warning color classes", () => {
    render(<Badge color="warning">pending</Badge>);
    const badge = screen.getByText("pending");
    expect(badge.className).toContain("bg-warning");
    expect(badge.className).toContain("text-warning");
  });

  it("renders as a span element", () => {
    render(<Badge>tag</Badge>);
    const badge = screen.getByText("tag");
    expect(badge.tagName).toBe("SPAN");
  });
});
