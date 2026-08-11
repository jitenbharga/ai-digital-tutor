import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { Brain, Send, AlertTriangle, CheckCircle2, XCircle, History, ChevronDown, ChevronUp, Loader2, RotateCcw, ArrowRight } from 'lucide-react';

const VERDICT_STYLES = {
  solid:  { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-700', label: 'Solid understanding' },
  partial:{ bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', label: 'Getting there' },
  shaky:  { bg: 'bg-red-50',   border: 'border-red-200',   text: 'text-red-700',   label: 'Shaky — revisit' },
};

function ScoreRing({ score }) {
  const r = 44, c = 2 * Math.PI * r;
  const offset = c - (score / 100) * c;
  const color = score >= 70 ? '#22c55e' : score >= 40 ? '#f59e0b' : '#ef4444';
  return (
    <svg width="110" height="110" className="mx-auto">
      <circle cx="55" cy="55" r={r} fill="none" stroke="#eef2ff" strokeWidth="9" />
      <circle cx="55" cy="55" r={r} fill="none" stroke={color} strokeWidth="9"
        strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
        transform="rotate(-90 55 55)" className="transition-all duration-1000" />
      <text x="55" y="55" textAnchor="middle" dy="0.35em" className="text-3xl font-extrabold" fill={color}>{score}</text>
    </svg>
  );
}

function ResultCard({ result, onChallenge, onRetry }) {
  const v = VERDICT_STYLES[result.verdict] || VERDICT_STYLES.partial;
  return (
    <div className="space-y-4 animate-scale-in">
      <div className={`rounded-2xl border p-5 text-center ${v.bg} ${v.border}`}>
        <ScoreRing score={result.score} />
        <p className={`font-bold mt-2 ${v.text}`}>{v.label}</p>
      </div>

      {/* Sub-scores */}
      <div className="grid grid-cols-3 gap-2.5 text-center">
        {['correctness', 'completeness', 'clarity'].map(k => (
          <div key={k} className="card-tight py-3">
            <div className="text-lg font-extrabold text-ink">{result[k] ?? '—'}<span className="text-sm text-ink-faint">/10</span></div>
            <div className="text-[11px] text-ink-muted capitalize">{k}</div>
          </div>
        ))}
      </div>

      {result.what_was_good && (
        <div className="bg-green-50 border border-green-100 rounded-xl p-3.5">
          <div className="flex items-center gap-1.5 text-green-700 text-xs font-bold mb-1"><CheckCircle2 size={14} /> What was good</div>
          <p className="text-sm text-green-800">{result.what_was_good}</p>
        </div>
      )}

      {result.gaps?.length > 0 && (
        <div className="bg-amber-50 border border-amber-100 rounded-xl p-3.5">
          <div className="flex items-center gap-1.5 text-amber-700 text-xs font-bold mb-1.5"><AlertTriangle size={14} /> You skipped</div>
          <ul className="text-sm text-amber-800 space-y-1">
            {result.gaps.map((g, i) => <li key={i} className="flex gap-2"><span className="text-amber-400">→</span>{g}</li>)}
          </ul>
        </div>
      )}

      {result.misconceptions?.length > 0 && (
        <div className="bg-red-50 border border-red-100 rounded-xl p-3.5">
          <div className="flex items-center gap-1.5 text-red-700 text-xs font-bold mb-1.5"><XCircle size={14} /> Actually wrong</div>
          <ul className="text-sm text-red-800 space-y-1">
            {result.misconceptions.map((m, i) => <li key={i} className="flex gap-2"><span className="text-red-400">✗</span>{m}</li>)}
          </ul>
          {result.misconceptions_added > 0 && (
            <p className="text-xs text-red-500 mt-2">Added {result.misconceptions_added} to your mistakes notebook</p>
          )}
        </div>
      )}

      {result.challenge_question && (
        <div className="bg-brand-50 border border-brand-100 rounded-xl p-3.5">
          <div className="text-xs font-bold text-brand-700 mb-1">Challenge question</div>
          <p className="text-sm text-ink-soft">{result.challenge_question}</p>
          <button onClick={onChallenge} className="mt-2 text-xs text-brand-600 hover:text-brand-800 font-semibold flex items-center gap-1">
            Work through it with the tutor <ArrowRight size={12} />
          </button>
        </div>
      )}

      <button onClick={onRetry} className="btn-secondary w-full"><RotateCcw size={16} /> Explain another concept</button>
    </div>
  );
}

export default function Feynman() {
  const navigate = useNavigate();
  const [topic, setTopic] = useState('');
  const [explanation, setExplanation] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    api.getFeynmanHistory().then(r => setHistory(r.attempts || [])).catch(() => {});
  }, [result]);

  const submit = async () => {
    if (!topic.trim() || !explanation.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.evaluateFeynman(topic.trim(), explanation.trim());
      setResult(res);
    } catch (e) {
      setError(e.message || 'Failed to evaluate');
    } finally { setLoading(false); }
  };

  const handleChallenge = () => {
    if (result?.challenge_question) navigate('/ask', { state: { prefill: result.challenge_question } });
  };
  const reset = () => { setResult(null); setExplanation(''); };

  const charCount = explanation.length;
  const charColor = charCount < 30 ? 'text-red-400' : charCount > 5500 ? 'text-amber-500' : 'text-ink-faint';

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-6 animate-fade-in">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 bg-gradient-to-br from-purple-500 to-fuchsia-600 text-white rounded-2xl mb-3 shadow-soft">
          <Brain size={26} />
        </div>
        <h2 className="text-2xl font-extrabold text-ink">Explain it back</h2>
        <p className="text-ink-muted text-sm mt-1">If you can't explain it simply, you don't understand it yet</p>
      </div>

      {!result ? (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-semibold text-ink-soft mb-1.5">What are you explaining?</label>
            <input value={topic} onChange={e => setTopic(e.target.value)}
              placeholder="e.g. Quadratic equations, Newton's 3rd law…" className="input-field" />
          </div>

          <div>
            <label className="block text-sm font-semibold text-ink-soft mb-1.5">Explain it like teaching a 12-year-old</label>
            <textarea value={explanation} onChange={e => setExplanation(e.target.value)}
              placeholder="In your own words — no peeking at notes. Include the WHY, not just the what…"
              rows={8} className="input-field resize-y" />
            <div className={`text-xs mt-1 text-right ${charColor}`}>{charCount}/6000 {charCount < 30 && '(min 30)'}</div>
          </div>

          {error && <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{error}</div>}

          <button onClick={submit} disabled={loading || !topic.trim() || charCount < 30} className="btn-primary w-full py-3">
            {loading ? <><Loader2 size={18} className="animate-spin" /> Checking your understanding…</> : <><Send size={18} /> Grade my explanation</>}
          </button>
        </div>
      ) : (
        <ResultCard result={result} onChallenge={handleChallenge} onRetry={reset} />
      )}

      {/* History */}
      {history.length > 0 && (
        <div className="card">
          <button onClick={() => setShowHistory(s => !s)} className="w-full flex items-center justify-between">
            <h3 className="section-title"><History size={16} className="text-ink-muted" /> Past explain-backs</h3>
            {showHistory ? <ChevronUp size={16} className="text-ink-faint" /> : <ChevronDown size={16} className="text-ink-faint" />}
          </button>
          {showHistory && (
            <div className="space-y-1.5 mt-3">
              {history.slice(0, 8).map((a, i) => (
                <div key={i} className="flex items-center gap-3 text-sm">
                  <span className={`font-bold w-8 text-right ${a.score >= 70 ? 'text-green-600' : a.score >= 40 ? 'text-amber-600' : 'text-red-600'}`}>{a.score}</span>
                  <span className="text-ink-soft flex-1 truncate capitalize">{a.topic}</span>
                  <span className="text-xs text-ink-faint">{a.created_at ? new Date(a.created_at * 1000).toLocaleDateString() : ''}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
