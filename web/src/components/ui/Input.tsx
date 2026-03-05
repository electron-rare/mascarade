import { InputHTMLAttributes } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export default function Input({ label, className = "", ...props }: Props) {
  return (
    <div>
      {label && (
        <label className="block text-[11px] text-muted mb-1 uppercase tracking-wide">{label}</label>
      )}
      <input
        className={`w-full bg-bg border border-border rounded px-3 py-2 text-sm text-amber-100 outline-none focus:border-accent focus:shadow-[0_0_0_2px_rgba(255,209,102,0.08)] transition-colors placeholder:text-muted/60 ${className}`}
        {...props}
      />
    </div>
  );
}
