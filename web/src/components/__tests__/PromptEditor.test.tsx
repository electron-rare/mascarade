import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import PromptEditor from "../PromptEditor";

// Mock Monaco Editor — it requires a browser-like environment that jsdom cannot fully provide
vi.mock("@monaco-editor/react", () => ({
  default: ({ value, onChange }: { value: string; onChange?: (v: string) => void }) => (
    <textarea
      data-testid="mock-monaco"
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
    />
  ),
}));

// Mock DOMPurify
vi.mock("dompurify", () => ({
  default: {
    sanitize: (html: string) => html,
  },
}));

describe("PromptEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders without crash in edit mode by default", () => {
    render(<PromptEditor value="Hello world" />);
    expect(screen.getByTestId("mock-monaco")).toBeInTheDocument();
    expect(screen.getByText("Edit")).toBeInTheDocument();
    expect(screen.getByText("Preview")).toBeInTheDocument();
  });

  it("renders label when provided", () => {
    render(<PromptEditor value="" label="System Prompt" />);
    expect(screen.getByText("System Prompt")).toBeInTheDocument();
  });

  it("switches to preview mode and renders markdown as HTML", async () => {
    const user = userEvent.setup();
    render(<PromptEditor value="# Title" />);

    const previewBtn = screen.getByText("Preview");
    await user.click(previewBtn);

    // In preview mode the markdown should be rendered as HTML
    expect(screen.getByText("Title")).toBeInTheDocument();
  });

  it("shows placeholder text in preview when value is empty", async () => {
    const user = userEvent.setup();
    render(<PromptEditor value="" placeholder="Write something" />);

    await user.click(screen.getByText("Preview"));
    expect(screen.getByText("Write something")).toBeInTheDocument();
  });

  it("shows default placeholder when value is empty and no placeholder provided", async () => {
    const user = userEvent.setup();
    render(<PromptEditor value="" />);

    await user.click(screen.getByText("Preview"));
    expect(screen.getByText("No content to preview")).toBeInTheDocument();
  });

  it("calls onChange when editor value changes", async () => {
    const handleChange = vi.fn();
    const user = userEvent.setup();
    render(<PromptEditor value="" onChange={handleChange} />);

    const textarea = screen.getByTestId("mock-monaco");
    await user.type(textarea, "x");
    expect(handleChange).toHaveBeenCalled();
  });

  it("renders bold markdown in preview via DOMPurify sanitize", async () => {
    const user = userEvent.setup();
    render(<PromptEditor value="**bold text**" />);

    await user.click(screen.getByText("Preview"));
    expect(screen.getByText("bold text")).toBeInTheDocument();
  });
});
