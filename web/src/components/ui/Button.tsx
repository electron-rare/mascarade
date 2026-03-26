import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variants: Record<Variant, string> = {
  primary:
    "bg-accent text-white shadow-apple hover:shadow-apple-md hover:brightness-110",
  secondary:
    "bg-surface text-[#1d1d1f] border border-[rgba(0,0,0,0.06)] hover:border-[rgba(0,0,0,0.16)] hover:bg-[#ededf0]",
  danger:
    "bg-error/8 text-error border border-error/15 hover:bg-error/12 hover:border-error/25",
  ghost:
    "bg-transparent text-muted border border-transparent hover:bg-surface hover:text-[#1d1d1f]",
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
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-full px-5 py-2",
        "font-sans text-sm font-semibold transition-all duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
        "disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        className,
      ].join(" ")}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <span className="animate-spin text-[11px]">&#x27F3;</span>}
      {children}
    </button>
  );
}
