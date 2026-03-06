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
        "rounded-[1.75rem] border border-border/80",
        "bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,8,7,0.98))]",
        "shadow-[0_0_28px_rgba(0,0,0,0.28)] transition-all duration-200",
        "hover:border-accent/22 hover:shadow-[0_18px_45px_rgba(0,0,0,0.34)]",
        className,
      ].join(" ")}
    >
      {title && (
        <div className="border-b border-border/80 bg-black/25 px-5 py-4">
          <p className="screen-label">panel</p>
          <h3 className="mt-2 text-sm font-semibold uppercase tracking-[0.18em] text-accent glow-text">
            {title}
          </h3>
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}
