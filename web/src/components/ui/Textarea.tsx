import { TextareaHTMLAttributes } from "react";

interface Props extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
}

export default function Textarea({ label, className = "", ...props }: Props) {
  return (
    <div>
      {label && (
        <label className="block text-xs text-muted mb-1">{label}</label>
      )}
      <textarea
        className={`w-full bg-bg border border-border rounded px-3 py-2 text-sm text-slate-200 outline-none focus:border-accent transition-colors placeholder:text-muted/50 resize-y min-h-[80px] ${className}`}
        {...props}
      />
    </div>
  );
}
