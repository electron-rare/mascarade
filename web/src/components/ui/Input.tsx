import { InputHTMLAttributes } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export default function Input({ label, className = "", ...props }: Props) {
  return (
    <div>
      {label && (
        <label className="block text-xs text-muted mb-1">{label}</label>
      )}
      <input
        className={`w-full bg-bg border border-border rounded px-3 py-2 text-sm text-slate-200 outline-none focus:border-accent transition-colors placeholder:text-muted/50 ${className}`}
        {...props}
      />
    </div>
  );
}
