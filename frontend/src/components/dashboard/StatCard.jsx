/* Presentational stat tile. Extracted from Dashboard.jsx (W6). */
export default function StatCard({
  icon: Icon,
  label,
  value,
  color = 'text-brand-600',
  bg = 'bg-brand-50',
}) {
  return (
    <div className="card flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${bg}`}>
        <Icon className={color} size={22} />
      </div>
      <div>
        <p className="text-sm text-ink-muted">{label}</p>
        <p className="font-display text-2xl font-semibold text-ink">{value}</p>
      </div>
    </div>
  );
}