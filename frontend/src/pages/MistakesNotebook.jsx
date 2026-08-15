import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { AlertCircle, CheckCircle2, ChevronDown, ChevronRight, Filter, BookOpen, Zap, Brain, Loader2 } from 'lucide-react';

const SOURCE_STYLES = {
  quiz:  { label: 'Quiz', bg: 'bg-teal-50', text: 'text-teal-700' },
  tutor: { label: 'Tutor', bg: 'bg-blue-50', text: 'text-blue-700' },
};

function MistakeCard({ mistake, onResolve, onLocalResolve }) {
  const [open, setOpen] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [showExplain, setShowExplain] = useState(false);
  const [explainText, setExplainText] = useState('');
  const [grading, setGrading] = useState(false);
  const [grade, setGrade] = useState(null);
  const src = SOURCE_STYLES[mistake.source] || SOURCE_STYLES.tutor;

  const handleResolve = async () => {
    setResolving(true);
    try { await onResolve(mistake.mistake_id); }
    finally { setResolving(false); }
  };

  const submitExplain = async () => {
    if (grading || explainText.trim().length < 20) return;
    setGrading(true);
    setGrade(null);
    try {
      const r = await api.explainMistake(mistake.mistake_id, explainText.trim());
      setGrade(r);
      if (r.resolved) {
        // Let them read the feedback, then mark it resolved in the list.
        setTimeout(() => onLocalResolve?.(mistake.mistake_id), 1400);
      }
    } catch (e) {
      setGrade({ understood: false, score: 0, feedback: e.message || 'Try again', still_missing: [] });
    } finally {
      setGrading(false);
    }
  };

  const timeAgo = () => {
    const hrs = (Date.now() / 1000 - mistake.timestamp) / 3600;
    if (hrs < 1) return 'Just now';
    if (hrs < 24) return `${Math.round(hrs)}h ago`;
    const days = Math.round(hrs / 24);
    return `${days}d ago`;
  };

  return (
    <div className={`border rounded-xl overflow-hidden transition-all ${
      mistake.resolved ? 'border-green-200 bg-green-50/30' : 'border-red-200 bg-white'
    }`}>
      {/* Header */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50/50 transition-colors"
      >
        {mistake.resolved
          ? <CheckCircle2 size={18} className="text-green-500 flex-shrink-0" />
          : <AlertCircle size={18} className="text-red-400 flex-shrink-0" />
        }
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium truncate ${mistake.resolved ? 'text-gray-500 line-through' : 'text-gray-900'}`}>
            {mistake.question || 'No question recorded'}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${src.bg} ${src.text}`}>
              {src.label}
            </span>
            {mistake.topic && (
              <span className="text-xs text-gray-400 capitalize">{mistake.topic}</span>
            )}
            <span className="text-xs text-gray-300">{timeAgo()}</span>
          </div>
        </div>
        {open ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-3">
          {mistake.user_answer && (
            <div>
              <p className="text-xs font-medium text-red-600 mb-0.5">Your answer</p>
              <p className="text-sm text-gray-700 bg-red-50 rounded-lg px-3 py-2">{mistake.user_answer}</p>
            </div>
          )}
          {mistake.correct_answer && (
            <div>
              <p className="text-xs font-medium text-green-600 mb-0.5">Correct answer</p>
              <p className="text-sm text-gray-700 bg-green-50 rounded-lg px-3 py-2">{mistake.correct_answer}</p>
            </div>
          )}
          {mistake.explanation && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-xs font-semibold text-blue-700 mb-1 flex items-center gap-1">
                <BookOpen size={12} /> Explanation
              </p>
              <p className="text-sm text-blue-900">{mistake.explanation}</p>
            </div>
          )}
          {mistake.concept && (
            <p className="text-xs text-gray-400">Concept: <span className="text-gray-600">{mistake.concept}</span></p>
          )}

          {!mistake.resolved && !showExplain && (
            <div className="flex gap-2">
              <button
                onClick={() => { setShowExplain(true); setGrade(null); }}
                className="flex-1 py-2 text-[#201a0e] text-sm font-medium rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-1.5 hover:-translate-y-px"
                  style={{ background: 'linear-gradient(180deg,#ecd9a8,#cfa654)' }}
                >
                  <Brain size={14} /> Explain it back
              </button>
              <button
                onClick={handleResolve}
                disabled={resolving}
                className="py-2 px-3 bg-green-500 hover:bg-green-600 text-white text-sm font-medium rounded-xl transition-colors disabled:opacity-50 flex items-center gap-1.5"
                title="Just mark as understood"
              >
                <CheckCircle2 size={14} /> {resolving ? '…' : 'Got it'}
              </button>
            </div>
          )}

          {!mistake.resolved && showExplain && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500">In your own words: why was this wrong, and what's the correct idea? (Explaining it back makes it stick.)</p>
              <textarea
                rows={3}
                className="input-field w-full text-sm resize-none"
                placeholder="e.g. I applied the power rule but forgot the chain rule; the correct step is…"
                value={explainText}
                onChange={e => setExplainText(e.target.value)}
              />
              {grade && (
                <div className={`rounded-lg p-2.5 text-sm border ${grade.understood ? 'bg-green-50 border-green-200 text-green-800' : 'bg-amber-50 border-amber-200 text-amber-900'}`}>
                  <p className="font-semibold flex items-center gap-1.5">
                    {grade.understood ? <CheckCircle2 size={14} className="text-green-600" /> : <AlertCircle size={14} className="text-amber-600" />}
                    {grade.understood ? `Nailed it — ${grade.score}%` : `Almost — ${grade.score}%`}
                  </p>
                  {grade.feedback && <p className="mt-0.5">{grade.feedback}</p>}
                  {!grade.understood && grade.still_missing?.length > 0 && (
                    <ul className="list-disc list-inside mt-1 text-xs">
                      {grade.still_missing.map((g, i) => <li key={i}>{g}</li>)}
                    </ul>
                  )}
                  {grade.resolved && <p className="mt-1 text-xs font-medium">Marked as understood ✓</p>}
                </div>
              )}
              <div className="flex gap-2">
                <button
                  onClick={submitExplain}
                  disabled={grading || explainText.trim().length < 20}
                  className="flex-1 py-2 text-[#201a0e] text-sm font-medium rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-1.5 hover:-translate-y-px"
                  style={{ background: 'linear-gradient(180deg,#ecd9a8,#cfa654)' }}
                >
                  {grading ? <><Loader2 size={14} className="animate-spin" /> Grading…</> : 'Submit explanation'}
                </button>
                <button
                  onClick={() => { setShowExplain(false); setGrade(null); }}
                  className="py-2 px-3 bg-gray-100 hover:bg-gray-200 text-gray-600 text-sm font-medium rounded-xl transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function MistakesNotebook() {
  const navigate = useNavigate();
  const [mistakes, setMistakes] = useState([]);
  const [stats, setStats] = useState({ total: 0, unresolved: 0 });
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('unresolved'); // 'all' | 'unresolved' | 'resolved'

  const load = async () => {
    setLoading(true);
    try {
      const resolved = filter === 'all' ? null : filter === 'resolved';
      const data = await api.getMistakes(null, resolved);
      setMistakes(data.mistakes || []);
      setStats({ total: data.total, unresolved: data.unresolved });
    } catch (e) {
      console.error('Failed to load mistakes:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [filter]);

  // Update local state only (server already resolved via explain-back).
  const markResolvedLocal = (mistakeId) => {
    setMistakes(prev => prev.map(m =>
      m.mistake_id === mistakeId ? { ...m, resolved: true } : m
    ));
    setStats(prev => ({ ...prev, unresolved: Math.max(0, prev.unresolved - 1) }));
  };

  const handleResolve = async (mistakeId) => {
    await api.resolveMistake(mistakeId);
    markResolvedLocal(mistakeId);
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Zap size={20} className="text-red-500" />
            Mistakes Notebook
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {stats.unresolved > 0
              ? `${stats.unresolved} mistake${stats.unresolved > 1 ? 's' : ''} to review`
              : 'All caught up!'
            }
          </p>
        </div>
        <span className="text-sm text-gray-400">{stats.total} total</span>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {[
          { key: 'unresolved', label: 'To Review' },
          { key: 'resolved', label: 'Resolved' },
          { key: 'all', label: 'All' },
        ].map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-all ${
              filter === f.key
                ? 'text-[#201a0e]'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
            style={filter === f.key ? { background: 'linear-gradient(180deg,#ecd9a8,#cfa654)' } : undefined}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Mistakes list */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin h-8 w-8 border-4 border-brand-500 border-t-transparent rounded-full" />
        </div>
      ) : mistakes.length === 0 ? (
        <div className="text-center py-12">
          <div className="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 size={32} className="text-green-500" />
          </div>
          <p className="text-gray-500">
            {filter === 'unresolved' ? 'No unresolved mistakes!' : 'No mistakes found.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {mistakes.map(m => (
            <MistakeCard key={m.mistake_id} mistake={m} onResolve={handleResolve} onLocalResolve={markResolvedLocal} />
          ))}
        </div>
      )}
    </div>
  );
}
