export default function Spinner({ className = "" }: { className?: string }) {
  return (
    <div
      className={`h-6 w-6 animate-spin rounded-full border-2 border-border/80 border-t-accent shadow-[0_0_12px_rgba(255,209,102,0.28)] ${className}`}
    />
  );
}
