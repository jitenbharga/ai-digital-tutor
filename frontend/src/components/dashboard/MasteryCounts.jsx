import { Sparkles } from 'lucide-react';

/* Mastery overview counts + stacked progress bar. Extracted from Dashboard.jsx (W6). */
export default function MasteryCounts({ counts }) {
  if (!counts) return null;
  const total = counts.total || 1;
  const pct = (n) => Math.round((n / total) * 100);

  return (
    <div className="card">
      <h3 className="font-semibold text-ink mb-4 flex items-center gap-2">
        <Sparkles size={18} className="text-brand-500" /> Mastery Overview
      </h3>
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center">
          <div className="font-display text-3xl font-semibold text-green-600">{counts.mastered}</div>
          <div className="text-xs text-ink-muted">Mastered</div>
        </div>
        <div className="text-center">
          <div className="font-display text-3xl font-semibold text-amber-500">{counts.in_progress}</div>
          <div className="text-xs text-ink-muted">In Progress</div>
        </div>
        <div className="text-center">
          <div className="font-display text-3xl font-semibold text-ink-faint">{counts.not_started}</div>
          <div className="text-xs text-ink-muted">Not Started</div>
        </div>
      </div>
      {/* Stacked progress bar */}
      <div className="flex h-3 rounded-full overflow-hidden" style={{ background: 'var(--bd2)' }}>
        {counts.mastered > 0 && (
          <div className="bg-green-500 transition-all duration-700" style={{ width: `${pct(counts.mastered)}%` }} />
        )}
        {counts.in_progress > 0 && (
          <div className="bg-amber-400 transition-all duration-700" style={{ width: `${pct(counts.in_progress)}%` }} />
        )}
      </div>
      <div className="flex justify-between text-xs text-ink-faint mt-1">
        <span>{pct(counts.mastered)}% mastered</span>
        <span>{counts.total} topics total</span>
      </div>
    </div>
  );
}