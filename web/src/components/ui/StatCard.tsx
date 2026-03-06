export default function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="bg-surface border border-border rounded-md p-4 glow-border hover:shadow-[0_0_16px_rgba(27,77,44,0.6),inset_0_0_12px_rgba(27,77,44,0.2)] transition-shadow duration-300">
      <p className="text-[11px] text-muted mb-1 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-accent glow-text">{value}</p>
      {sub && <p className="text-[11px] text-muted mt-1">{sub}</p>}
    </div>
  );
}
