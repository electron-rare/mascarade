type Color = "accent" | "error" | "warning" | "muted";

const colors: Record<Color, string> = {
  accent: "bg-accent/12 text-accent border-accent/40",
  error: "bg-error/10 text-error border-error/30",
  warning: "bg-warning/10 text-warning border-warning/30",
  muted: "bg-white/5 text-muted border-border",
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
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border uppercase tracking-wide ${colors[color]}`}
    >
      {children}
    </span>
  );
}
