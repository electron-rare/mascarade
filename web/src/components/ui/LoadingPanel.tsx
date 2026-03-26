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
        "rounded-apple-lg border border-[rgba(0,0,0,0.06)] bg-surface",
        compact ? "px-5 py-6" : "px-6 py-12",
      ].join(" ")}
    >
      <div className="flex flex-col items-center text-center">
        <Spinner className="h-8 w-8" />
        <p className="text-xs text-muted mt-4">loading</p>
        <p className="mt-3 text-sm font-semibold text-[#1d1d1f]">{title}</p>
        <p className="mt-2 max-w-xl text-sm leading-6 text-muted">{message}</p>
        <div className="mt-5 grid w-full max-w-xl gap-2">
          <div className="h-3 animate-pulse rounded-full bg-[rgba(0,0,0,0.04)]" />
          <div className="h-3 animate-pulse rounded-full bg-[rgba(0,0,0,0.04)]" />
          <div className="h-3 w-2/3 animate-pulse rounded-full bg-[rgba(0,0,0,0.04)]" />
        </div>
      </div>
    </div>
  );
}
