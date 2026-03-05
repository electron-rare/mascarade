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
    <div className="bg-surface border border-border rounded-md p-4 shadow-[0_0_0_1px_rgba(255,209,102,0.03),0_0_14px_rgba(27,77,44,0.2)]">
      <p className="text-[11px] text-muted mb-1 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-accent">{value}</p>
      {sub && <p className="text-[11px] text-muted mt-1">{sub}</p>}
    </div>
  );
}
