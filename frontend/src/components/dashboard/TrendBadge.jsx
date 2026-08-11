import { ArrowUp, Target, TrendingUp } from 'lucide-react';

/* Trend indicator badge. Extracted from Dashboard.jsx (W6). */
export default function TrendBadge({ trend }) {
  const config = {
    improving: { icon: ArrowUp, text: 'Improving', color: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200' },
    steady: { icon: Target, text: 'Steady', color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200' },
    declining: { icon: TrendingUp, text: 'Needs Focus', color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200' },
  };
  const c = config[trend] || config.steady;
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium border ${c.bg} ${c.color} ${c.border}`}>
      <c.icon size={14} /> {c.text}
    </span>
  );
}
