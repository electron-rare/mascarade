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
      className={`bg-surface border border-border rounded-md shadow-[0_0_0_1px_rgba(255,209,102,0.03),0_0_18px_rgba(27,77,44,0.22)] ${className}`}
    >
      {title && (
        <div className="px-4 py-3 border-b border-border bg-black/35">
          <h3 className="text-sm font-semibold text-accent uppercase tracking-wide">{title}</h3>
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}
