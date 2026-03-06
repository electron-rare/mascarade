import { ReactNode } from "react";

export default function Card({
  children,
  className = "",
  title,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <div
      className={`bg-surface border border-border rounded-md glow-border hover:shadow-[0_0_16px_rgba(27,77,44,0.6),inset_0_0_12px_rgba(27,77,44,0.2)] transition-shadow duration-300 ${className}`}
    >
      {title && (
        <div className="px-4 py-3 border-b border-border bg-black/35">
          <h3 className="text-sm font-semibold text-accent uppercase tracking-wide glow-text glitch">{title}</h3>
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}
