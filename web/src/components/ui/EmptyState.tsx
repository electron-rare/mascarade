export default function EmptyState({
  message,
  action,
}: {
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center border border-border rounded-md bg-black/25">
      <p className="text-muted text-sm uppercase tracking-wide">{message}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
