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
        <label className="block text-[11px] text-muted mb-1 uppercase tracking-wide">{label}</label>
      )}
      <select
        className={`w-full bg-bg border border-border rounded px-3 py-2 text-sm text-amber-100 outline-none focus:border-accent focus:shadow-[0_0_0_2px_rgba(255,209,102,0.08)] transition-colors ${className}`}
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
