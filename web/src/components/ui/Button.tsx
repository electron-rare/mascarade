import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-black hover:bg-[#ffdc86]",
  secondary: "bg-surface border border-border text-accent hover:bg-white/5",
  danger: "bg-error/10 text-error border border-error/30 hover:bg-error/20",
  ghost: "text-muted hover:text-accent hover:bg-white/5",
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
      className={`inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none border border-transparent ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <span className="animate-spin text-xs">⟳</span>}
      {children}
    </button>
  );
}
