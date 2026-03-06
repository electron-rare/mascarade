export default function EmptyState({
  message,
  action,
}: {
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[1.75rem] border border-border/80 bg-[linear-gradient(180deg,rgba(8,9,8,0.84),rgba(6,6,6,0.94))] px-6 py-12 text-center">
      <p className="screen-label">empty lane</p>
      <p className="mt-3 max-w-xl text-sm uppercase tracking-[0.18em] text-muted">{message}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
