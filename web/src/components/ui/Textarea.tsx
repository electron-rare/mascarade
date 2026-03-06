import { TextareaHTMLAttributes, useId } from "react";

interface Props extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
}

export default function Textarea({ label, className = "", id: externalId, ...props }: Props) {
  const autoId = useId();
  const id = externalId || autoId;

  return (
    <div className="space-y-2">
      {label && (
        <label htmlFor={id} className="block text-[11px] uppercase tracking-[0.18em] text-muted">
          {label}
        </label>
      )}
      <textarea
        id={id}
        className={[
          "min-h-[120px] w-full resize-y rounded-[1.5rem] border border-border/80 bg-black/30 px-4 py-3",
          "text-sm text-amber-100 outline-none transition-all placeholder:text-muted/60",
          "focus:border-accent/45 focus:bg-black/40 focus:shadow-[0_0_0_2px_rgba(255,209,102,0.08)]",
          className,
        ].join(" ")}
        {...props}
      />
    </div>
  );
}
