import { Sparkles } from 'lucide-react';

/* Mastery overview counts + stacked progress bar. Extracted from Dashboard.jsx (W6). */
export default function MasteryCounts({ counts }) {
  if (!counts) return null;
  const total = counts.total || 1;
  const pct = (n) => Math.round((n / total) * 100);

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Sparkles size={18} className="text-brand-500" /> Mastery Overview
      </h3>
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-green-600">{counts.mastered}</div>
          <div className="text-xs text-gray-500">Mastered</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-amber-500">{counts.in_progress}</div>
          <div className="text-xs text-gray-500">In Progress</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-gray-400">{counts.not_started}</div>
          <div className="text-xs text-gray-500">Not Started</div>
        </div>
      </div>
      {/* Stacked progress bar */}
      <div className="flex h-3 rounded-full overflow-hidden bg-gray-100">
        {counts.mastered > 0 && (
          <div className="bg-green-500 transition-all duration-700" style={{ width: `${pct(counts.mastered)}%` }} />
        )}
        {counts.in_progress > 0 && (
          <div className="bg-amber-400 transition-all duration-700" style={{ width: `${pct(counts.in_progress)}%` }} />
        )}
      </div>
      <div className="flex justify-between text-xs text-gray-400 mt-1">
        <span>{pct(counts.mastered)}% mastered</span>
        <span>{counts.total} topics total</span>
      </div>
    </div>
  );
}
