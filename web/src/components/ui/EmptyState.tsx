export default function EmptyState({
  message,
  action,
}: {
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-apple-lg border border-[rgba(0,0,0,0.06)] bg-surface px-6 py-12 text-center">
      <p className="text-xs text-muted">empty</p>
      <p className="mt-3 max-w-xl text-sm text-muted">{message}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
