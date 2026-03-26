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
        <label htmlFor={id} className="block text-xs font-medium text-muted">
          {label}
        </label>
      )}
      <textarea
        id={id}
        className={[
          "min-h-[120px] w-full resize-y rounded-xl border border-[rgba(0,0,0,0.12)] bg-white px-4 py-3",
          "text-sm text-[#1d1d1f] outline-none transition-all placeholder:text-[#86868b]",
          "focus:border-accent focus:shadow-[0_0_0_3px_rgba(0,113,227,0.12)]",
          className,
        ].join(" ")}
        {...props}
      />
    </div>
  );
}
