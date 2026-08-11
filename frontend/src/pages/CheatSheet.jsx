import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import Markdown from '../components/Markdown';
import { ArrowLeft, FileText, Loader2, Download, RefreshCw, AlertTriangle, Sparkles } from 'lucide-react';

/**
 * D2: Smart cheat sheet — one-page formulas + definitions + YOUR personal
 * gotchas (built from your real mistakes). Cached; refreshable; PDF export.
 */
export default function CheatSheet() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const studentId = user?.username || 'anon';
  const [topic, setTopic] = useState('');
  const [studied, setStudied] = useState([]);
  const [sheet, setSheet] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.knowledgeGraph(studentId)
      .then(d => setStudied([...new Set((d?.nodes || []).map(n => n.topic))].slice(0, 8)))
      .catch(() => {});
  }, [studentId]);

  const gen = async (t, refresh = false) => {
    const tp = (t || topic).trim();
    if (!tp || loading) return;
    setTopic(tp); setLoading(true); setError(''); if (!refresh) setSheet(null);
    try {
      setSheet(await api.makeCheatsheet(tp, refresh));
    } catch (e) { setError(e.message || 'Failed to build'); }
    finally { setLoading(false); }
  };

  const download = async () => {
    try {
      const blob = await api.cheatsheetPdf(sheet.topic);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `cheatsheet_${sheet.topic}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setError(e.message); }
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-5 animate-fade-in">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/')} className="btn-ghost !px-2"><ArrowLeft size={20} /></button>
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Cheat sheet</h2>
          <p className="text-xs text-slate-500">Formulas, definitions + your personal gotchas — one page</p>
        </div>
      </div>

      {/* Topic input */}
      <div className="card-tight space-y-3">
        <div className="flex gap-2">
          <input className="input-field flex-1" placeholder="Topic (e.g. Trigonometry, Newton's laws)"
            value={topic} onChange={e => setTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && gen()} />
          <button onClick={() => gen()} className="btn-primary" disabled={!topic.trim() || loading}>
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
          </button>
        </div>
        {studied.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {studied.map(t => (
              <button key={t} onClick={() => gen(t)}
                className="text-xs px-2 py-1 rounded-lg bg-slate-100 text-slate-600 hover:bg-brand-50 hover:text-brand-700 transition-colors">{t}</button>
            ))}
          </div>
        )}
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{error}</div>}

      {loading && !sheet && (
        <div className="space-y-3">
          <div className="skeleton h-8 w-2/3" /><div className="skeleton h-24 w-full" /><div className="skeleton h-20 w-full" />
        </div>
      )}

      {/* Sheet */}
      {sheet && (
        <div className="card space-y-4 animate-scale-in">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-lg font-extrabold text-brand-700">{sheet.title}</h3>
            <div className="flex gap-1.5 flex-shrink-0">
              <button onClick={() => gen(sheet.topic, true)} className="btn-ghost !px-2" title="Refresh"><RefreshCw size={16} /></button>
              <button onClick={download} className="btn-ghost !px-2" title="Download PDF"><Download size={16} /></button>
            </div>
          </div>

          {sheet.key_formulas?.length > 0 && (
            <section>
              <h4 className="section-title mb-1.5">Key formulas</h4>
              <ul className="space-y-1 text-sm">{sheet.key_formulas.map((f, i) => <li key={i}><Markdown>{`• ${f}`}</Markdown></li>)}</ul>
            </section>
          )}
          {sheet.key_definitions?.length > 0 && (
            <section>
              <h4 className="section-title mb-1.5">Definitions</h4>
              <ul className="space-y-1 text-sm">{sheet.key_definitions.map((d, i) => (
                <li key={i}><span className="font-semibold">{d.term}</span> — <Markdown>{d.definition}</Markdown></li>
              ))}</ul>
            </section>
          )}
          {sheet.must_remember?.length > 0 && (
            <section>
              <h4 className="section-title mb-1.5">Must remember</h4>
              <ul className="space-y-1 text-sm list-disc list-inside">{sheet.must_remember.map((m, i) => <li key={i}>{m}</li>)}</ul>
            </section>
          )}
          {sheet.your_gotchas?.length > 0 ? (
            <section className="bg-amber-50 border border-amber-200 rounded-xl p-3">
              <h4 className="text-sm font-bold text-amber-800 flex items-center gap-1.5 mb-1.5"><AlertTriangle size={14} /> Your personal gotchas</h4>
              <ul className="space-y-1 text-sm text-amber-900">{sheet.your_gotchas.map((g, i) => <li key={i}>⚠ {g}</li>)}</ul>
            </section>
          ) : (
            <p className="text-xs text-slate-400 italic">No personal gotchas yet — take a quiz or explain-back so I can spot your recurring mistakes.</p>
          )}
          {sheet.quick_examples?.length > 0 && (
            <section>
              <h4 className="section-title mb-1.5">Quick examples</h4>
              <div className="space-y-2 text-sm">{sheet.quick_examples.map((ex, i) => <div key={i} className="bg-slate-50 rounded-lg p-2"><Markdown>{ex}</Markdown></div>)}</div>
            </section>
          )}

          <button onClick={download} className="btn-secondary w-full"><Download size={16} /> Download PDF</button>
        </div>
      )}
    </div>
  );
}
