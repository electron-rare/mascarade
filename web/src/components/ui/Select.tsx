import { SelectHTMLAttributes, useId } from "react";

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: { value: string; label: string }[];
}

export default function Select({
  label,
  options,
  className = "",
  id: externalId,
  ...props
}: Props) {
  const autoId = useId();
  const id = externalId || autoId;

  return (
    <div className="space-y-2">
      {label && (
        <label htmlFor={id} className="block text-xs font-medium text-muted">
          {label}
        </label>
      )}
      <select
        id={id}
        className={[
          "w-full rounded-xl border border-[rgba(0,0,0,0.12)] bg-white px-4 py-3 text-sm text-[#1d1d1f]",
          "outline-none transition-all focus:border-accent focus:shadow-[0_0_0_3px_rgba(0,113,227,0.12)]",
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
