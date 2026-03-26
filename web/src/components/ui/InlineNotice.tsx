type Tone = "info" | "success" | "error";

const tones: Record<Tone, string> = {
  info: "bg-surface text-[#1d1d1f]",
  success: "bg-success/8 text-success",
  error: "bg-error/8 text-error",
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
    <div className={["rounded-apple p-4", tones[tone], className].join(" ")}>
      <p className="text-[10px] font-semibold uppercase tracking-wide">{title}</p>
      <p className="mt-2 text-sm leading-6">{message}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
