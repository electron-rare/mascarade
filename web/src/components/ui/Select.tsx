import { SelectHTMLAttributes } from "react";

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: { value: string; label: string }[];
}

export default function Select({
  label,
  options,
  className = "",
  ...props
}: Props) {
  return (
    <div>
      {label && (
        <label className="block text-xs text-muted mb-1">{label}</label>
      )}
      <select
        className={`w-full bg-bg border border-border rounded px-3 py-2 text-sm text-slate-200 outline-none focus:border-accent transition-colors ${className}`}
        {...props}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
