import { TextareaHTMLAttributes } from "react";

interface Props extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
}

export default function Textarea({ label, className = "", ...props }: Props) {
  return (
    <div>
      {label && (
        <label className="block text-[11px] text-muted mb-1 uppercase tracking-wide">{label}</label>
      )}
      <textarea
        className={`w-full bg-bg border border-border rounded px-3 py-2 text-sm text-amber-100 outline-none focus:border-accent focus:shadow-[0_0_0_2px_rgba(255,209,102,0.08)] transition-colors placeholder:text-muted/60 resize-y min-h-[80px] ${className}`}
        {...props}
      />
    </div>
  );
}
