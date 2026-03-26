type Color = "accent" | "error" | "warning" | "muted";

const colors: Record<Color, string> = {
  accent: "bg-accent/8 text-accent",
  error: "bg-error/8 text-error",
  warning: "bg-warning/8 text-warning",
  muted: "bg-surface text-muted",
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
      className={`inline-flex min-h-8 items-center rounded-full px-3 py-1 text-[11px] font-semibold ${colors[color]}`}
    >
      {children}
    </span>
  );
}
