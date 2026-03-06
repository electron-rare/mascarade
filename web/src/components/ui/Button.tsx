import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variants: Record<Variant, string> = {
  primary:
    "border-accent/40 bg-accent/10 text-accent hover:bg-accent/16 hover:border-accent/55",
  secondary:
    "border-border/80 bg-black/25 text-amber-100/78 hover:border-accent/35 hover:text-accent hover:bg-black/35",
  danger:
    "border-error/35 bg-error/10 text-error hover:bg-error/18 hover:border-error/55",
  ghost:
    "border-border/70 bg-transparent text-muted hover:border-border/90 hover:bg-white/[0.03] hover:text-accent",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

export default function Button({
  variant = "primary",
  loading,
  className = "",
  children,
  disabled,
  ...props
}: Props) {
  return (
    <button
      className={[
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-2xl border px-4 py-2",
        "text-xs font-semibold uppercase tracking-[0.18em] transition-all duration-200",
        "disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        className,
      ].join(" ")}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <span className="animate-spin text-[11px]">⟳</span>}
      {children}
    </button>
  );
}
