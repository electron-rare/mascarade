export default function Spinner({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-spin rounded-full border-2 border-border border-t-accent w-5 h-5 ${className}`}
    />
  );
}
