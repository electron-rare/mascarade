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
    <div className="space-y-2">
      {label && (
        <label className="block text-[11px] uppercase tracking-[0.18em] text-muted">{label}</label>
      )}
      <select
        className={[
          "w-full rounded-2xl border border-border/80 bg-black/30 px-4 py-3 text-sm text-amber-100",
          "outline-none transition-all focus:border-accent/45 focus:bg-black/40 focus:shadow-[0_0_0_2px_rgba(255,209,102,0.08)]",
          className,
        ].join(" ")}
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
