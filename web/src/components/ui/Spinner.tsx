export default function Spinner({ className = "" }: { className?: string }) {
  return (
    <div
      className={`h-6 w-6 animate-spin rounded-full border-2 border-[rgba(0,0,0,0.1)] border-t-accent ${className}`}
    />
  );
}
