type Tone = "info" | "success" | "error";

const tones: Record<Tone, string> = {
  info: "border-border/80 bg-black/25 text-amber-100/72",
  success: "border-accent/30 bg-accent/8 text-accent",
  error: "border-error/35 bg-error/10 text-error",
};

export default function InlineNotice({
  title,
  message,
  tone = "info",
  action,
  className = "",
}: {
  title: string;
  message: string;
  tone?: Tone;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={["rounded-[1.5rem] border p-4", tones[tone], className].join(" ")}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em]">{title}</p>
      <p className="mt-2 text-sm leading-6">{message}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
