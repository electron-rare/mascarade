import { InputHTMLAttributes, useId } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export default function Input({ label, className = "", id: externalId, ...props }: Props) {
  const autoId = useId();
  const id = externalId || autoId;

  return (
    <div className="space-y-2">
      {label && (
        <label htmlFor={id} className="block text-[11px] uppercase tracking-[0.18em] text-muted">
          {label}
        </label>
      )}
      <input
        id={id}
        className={[
          "w-full rounded-2xl border border-border/80 bg-black/30 px-4 py-3 text-sm text-amber-100",
          "outline-none transition-all placeholder:text-muted/60",
          "focus:border-accent/45 focus:bg-black/40 focus:shadow-[0_0_0_2px_rgba(255,209,102,0.08)]",
          "focus-visible:ring-2 focus-visible:ring-accent/55 focus-visible:ring-offset-2 focus-visible:ring-offset-[#050505]",
          className,
        ].join(" ")}
        {...props}
      />
    </div>
  );
}
