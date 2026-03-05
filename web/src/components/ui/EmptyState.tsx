export default function EmptyState({
  message,
  action,
}: {
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <p className="text-muted text-sm">{message}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
