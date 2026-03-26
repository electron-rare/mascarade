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
    <div className="rounded-apple bg-white border border-[rgba(0,0,0,0.06)] p-4 shadow-apple transition-shadow duration-300 hover:shadow-apple-md">
      <p className="text-[11px] text-muted mb-1 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-accent">{value}</p>
      {sub && <p className="text-[11px] text-muted mt-1">{sub}</p>}
    </div>
  );
}
