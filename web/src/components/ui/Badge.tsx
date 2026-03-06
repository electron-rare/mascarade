type Color = "accent" | "error" | "warning" | "muted";

const colors: Record<Color, string> = {
  accent: "border-accent/35 bg-accent/10 text-accent",
  error: "border-error/35 bg-error/10 text-error",
  warning: "border-warning/35 bg-warning/10 text-warning",
  muted: "border-border/80 bg-black/25 text-muted",
};

export default function Badge({
  children,
  color = "muted",
}: {
  children: React.ReactNode;
  color?: Color;
}) {
  return (
    <span
      className={`inline-flex min-h-8 items-center rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${colors[color]}`}
    >
      {children}
    </span>
  );
}
