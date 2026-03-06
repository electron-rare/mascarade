import Spinner from "./Spinner";

export default function LoadingPanel({
  title = "Synchronizing lane",
  message = "Collecting the next runtime snapshot from the gateway.",
  compact = false,
}: {
  title?: string;
  message?: string;
  compact?: boolean;
}) {
  return (
    <div
      className={[
        "rounded-[1.75rem] border border-border/80 bg-[linear-gradient(180deg,rgba(8,9,8,0.84),rgba(6,6,6,0.94))]",
        compact ? "px-5 py-6" : "px-6 py-12",
      ].join(" ")}
    >
      <div className="flex flex-col items-center text-center">
        <Spinner className="h-8 w-8" />
        <p className="screen-label mt-4">loading lane</p>
        <p className="mt-3 text-sm font-semibold uppercase tracking-[0.18em] text-accent">{title}</p>
        <p className="mt-2 max-w-xl text-sm leading-6 text-amber-100/58">{message}</p>
        <div className="mt-5 grid w-full max-w-xl gap-2">
          <div className="h-3 animate-pulse rounded-full bg-white/8" />
          <div className="h-3 animate-pulse rounded-full bg-white/8" />
          <div className="h-3 w-2/3 animate-pulse rounded-full bg-white/8" />
        </div>
      </div>
    </div>
  );
}
