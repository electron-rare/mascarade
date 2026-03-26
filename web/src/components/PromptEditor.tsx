import { useId, useState } from "react";
import Editor from "@monaco-editor/react";

interface Props {
  label?: string;
  value: string;
  onChange?: (value: string) => void;
  disabled?: boolean;
  className?: string;
  id?: string;
  placeholder?: string;
}

type TabMode = "edit" | "preview";

export default function PromptEditor({
  label,
  value,
  onChange,
  disabled = false,
  className = "",
  id: externalId,
  placeholder,
}: Props) {
  const autoId = useId();
  const id = externalId || autoId;
  const [mode, setMode] = useState<TabMode>("edit");

  const handleEditorChange = (newValue: string | undefined) => {
    if (onChange && !disabled) {
      onChange(newValue || "");
    }
  };

  // Simple markdown-to-HTML converter for basic preview
  const renderMarkdown = (text: string): string => {
    let html = text;

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold text-accent mt-4 mb-2">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="text-xl font-semibold text-accent mt-5 mb-3">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold text-accent mt-6 mb-4">$1</h1>');

    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-[#1d1d1f]">$1</strong>');
    html = html.replace(/__(.*?)__/g, '<strong class="font-semibold text-[#1d1d1f]">$1</strong>');

    // Italic
    html = html.replace(/\*(.*?)\*/g, '<em class="italic text-[#6e6e73]">$1</em>');
    html = html.replace(/_(.*?)_/g, '<em class="italic text-[#6e6e73]">$1</em>');

    // Code blocks
    html = html.replace(/```([\s\S]*?)```/g, '<pre class="bg-[#f5f5f7] border border-[rgba(0,0,0,0.06)]/60 rounded-lg p-3 my-3 overflow-x-auto"><code class="text-sm text-accent/90">$1</code></pre>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code class="bg-[#f5f5f7] border border-[rgba(0,0,0,0.06)]/60 rounded px-1.5 py-0.5 text-sm text-accent/90">$1</code>');

    // Lists
    html = html.replace(/^\* (.*$)/gim, '<li class="ml-4 text-[#6e6e73]">• $1</li>');
    html = html.replace(/^- (.*$)/gim, '<li class="ml-4 text-[#6e6e73]">• $1</li>');

    // Line breaks
    html = html.replace(/\n\n/g, '<br/><br/>');
    html = html.replace(/\n/g, '<br/>');

    return html;
  };

  return (
    <div className={["space-y-2", className].join(" ")}>
      {label && (
        <label htmlFor={id} className="block text-[11px] uppercase tracking-[0.18em] text-muted">
          {label}
        </label>
      )}

      {/* Tab Navigation */}
      <div className="flex gap-1 rounded-t-[1.5rem] border border-b-0 border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-1">
        <button
          type="button"
          onClick={() => setMode("edit")}
          className={[
            "flex-1 rounded-xl px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition-all",
            mode === "edit"
              ? "bg-accent/10 text-accent border border-accent/40"
              : "text-[#6e6e73] hover:text-[#6e6e73] hover:bg-[#f5f5f7]",
          ].join(" ")}
        >
          Edit
        </button>
        <button
          type="button"
          onClick={() => setMode("preview")}
          className={[
            "flex-1 rounded-xl px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition-all",
            mode === "preview"
              ? "bg-accent/10 text-accent border border-accent/40"
              : "text-[#6e6e73] hover:text-[#6e6e73] hover:bg-[#f5f5f7]",
          ].join(" ")}
        >
          Preview
        </button>
      </div>

      {/* Content Area */}
      <div
        className={[
          "min-h-[400px] w-full overflow-hidden rounded-b-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7]",
          "focus-within:border-accent/45 focus-within:bg-[#f5f5f7] focus-within:shadow-[0_0_0_2px_rgba(255,209,102,0.08)]",
          disabled && "opacity-60 pointer-events-none",
        ].join(" ")}
      >
        {mode === "edit" ? (
          <Editor
            height="400px"
            language="markdown"
            value={value}
            onChange={handleEditorChange}
            theme="vs-dark"
            options={{
              readOnly: disabled,
              minimap: { enabled: false },
              fontSize: 14,
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              wordWrap: "on",
              wrappingStrategy: "advanced",
              padding: { top: 16, bottom: 16 },
              automaticLayout: true,
              tabSize: 2,
              insertSpaces: true,
              renderWhitespace: "selection",
              bracketPairColorization: { enabled: true },
              suggest: {
                showWords: true,
                showSnippets: true,
              },
            }}
          />
        ) : (
          <div className="min-h-[400px] overflow-y-auto p-4">
            {value ? (
              <div
                className="prose prose-invert max-w-none text-sm leading-7 text-[#6e6e73]"
                dangerouslySetInnerHTML={{ __html: renderMarkdown(value) }}
              />
            ) : (
              <p className="text-sm text-muted/60">
                {placeholder || "No content to preview"}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
