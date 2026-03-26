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
      className={[
        "rounded-apple-lg border border-[rgba(0,0,0,0.06)]",
        "bg-white",
        "shadow-apple-md transition-all duration-200",
        "hover:shadow-apple-lg hover:-translate-y-0.5",
        className,
      ].join(" ")}
    >
      {title && (
        <div className="border-b border-[rgba(0,0,0,0.06)] px-5 py-4">
          <p className="text-xs text-muted">panel</p>
          <h3 className="mt-1 text-sm font-semibold text-[#1d1d1f]">
            {title}
          </h3>
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}
