type Color = "accent" | "error" | "warning" | "muted";

const colors: Record<Color, string> = {
  accent: "bg-accent/10 text-accent border-accent/30",
  error: "bg-error/10 text-error border-error/30",
  warning: "bg-warning/10 text-warning border-warning/30",
  muted: "bg-white/5 text-muted border-white/10",
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
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${colors[color]}`}
    >
      {children}
    </span>
  );
}
