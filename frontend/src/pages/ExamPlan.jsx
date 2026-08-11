import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { ArrowLeft, CalendarDays, AlertTriangle, CheckCircle2, BookOpen, RefreshCw, TimerIcon, Trash2 } from 'lucide-react';

const ITEM_META = {
  revise:    { icon: BookOpen,  color: 'text-blue-600' },
  learn:     { icon: BookOpen,  color: 'text-blue-600' },
  revision:  { icon: RefreshCw, color: 'text-amber-600' },
  mock_exam: { icon: TimerIcon, color: 'text-red-600' },
};

/**
 * B4: Exam-date back-planning.
 * Pick subject + exam date + minutes/day → deterministic day-by-day plan
 * over the remaining curriculum, with a revision tail and a final mock exam.
 */
export default function ExamPlan() {
  const navigate = useNavigate();
  const [subjects, setSubjects] = useState([]);
  const [subject, setSubject] = useState('');
  const [examDate, setExamDate] = useState('');
  const [minutes, setMinutes] = useState(30);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [readiness, setReadiness] = useState(null);

  useEffect(() => {
    api.getSubjects()
      .then(r => {
        const subs = r?.subjects || r || [];
        setSubjects(subs.map(s => s.title || s.id || s));
      })
      .catch(() => {});
  }, []);

  // Try loading an existing plan + readiness when subject changes
  useEffect(() => {
    if (!subject) { setReadiness(null); return; }
    api.getExamPlan(subject).then(setPlan).catch(() => setPlan(null));
    api.examReadiness(subject).then(setReadiness).catch(() => setReadiness(null));
  }, [subject]);

  const build = async () => {
    setError('');
    setLoading(true);
    try {
      await api.createExamPlan({ subject, exam_date: examDate, daily_minutes: minutes });
      const p = await api.getExamPlan(subject);
      setPlan(p);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const removePlan = async () => {
    try { await api.deleteExamPlan(subject); setPlan(null); } catch {}
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/')} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={20} />
        </button>
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <CalendarDays size={20} className="text-brand-500" /> Exam plan
          </h2>
          <p className="text-xs text-gray-500">Exam date in → day-by-day plan out</p>
        </div>
      </div>

      {/* Builder form */}
      <div className="bg-white border border-gray-200 rounded-2xl p-4 space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
          <select className="input-field w-full" value={subject} onChange={e => setSubject(e.target.value)}>
            <option value="">Choose a subject…</option>
            {subjects.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">Exam date</label>
            <input type="date" className="input-field w-full" value={examDate}
              min={new Date(Date.now() + 86400000).toISOString().split('T')[0]}
              onChange={e => setExamDate(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Min/day</label>
            <select className="input-field" value={minutes} onChange={e => setMinutes(Number(e.target.value))}>
              <option value={15}>15</option>
              <option value={30}>30</option>
              <option value={60}>60</option>
              <option value={120}>120</option>
            </select>
          </div>
        </div>
        {error && <p className="text-red-600 text-sm bg-red-50 p-2 rounded-lg">{error}</p>}
        <button onClick={build} className="btn-primary w-full" disabled={!subject || !examDate || loading}>
          {loading ? 'Planning…' : plan ? 'Rebuild plan' : 'Build my plan'}
        </button>
      </div>

      {/* D3: Exam-readiness meter */}
      {readiness && (
        <div className="card">
          <div className="flex items-center gap-4">
            <div className="relative w-20 h-20 flex-shrink-0">
              <svg width="80" height="80" className="-rotate-90">
                <circle cx="40" cy="40" r="34" fill="none" stroke="#eef2ff" strokeWidth="8" />
                <circle cx="40" cy="40" r="34" fill="none" strokeWidth="8" strokeLinecap="round"
                  stroke={readiness.readiness_pct >= 75 ? '#22c55e' : readiness.readiness_pct >= 50 ? '#f59e0b' : '#ef4444'}
                  strokeDasharray={2 * Math.PI * 34}
                  strokeDashoffset={2 * Math.PI * 34 * (1 - readiness.readiness_pct / 100)}
                  className="transition-all duration-1000" />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-xl font-extrabold text-slate-900">{readiness.readiness_pct}%</span>
                <span className="text-[9px] text-slate-400">ready</span>
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-bold text-sm text-slate-900 capitalize">{readiness.subject} readiness</p>
              <p className="text-xs text-slate-500 mt-0.5">{readiness.verdict}</p>
              <p className="text-[11px] text-slate-400 mt-1">{readiness.studied_topics}/{readiness.total_topics} topics studied · {readiness.coverage_pct}% coverage</p>
            </div>
          </div>
          {readiness.weak_topics?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-100">
              <p className="text-xs font-semibold text-slate-600 mb-2">Weakest — fix these first:</p>
              <div className="space-y-1.5">
                {readiness.weak_topics.map((t, i) => (
                  <button key={i} onClick={() => navigate('/tutor', { state: { topic: t.topic, subject: readiness.subject } })}
                    className="w-full flex items-center gap-2 text-sm hover:bg-slate-50 rounded-lg px-2 py-1 -mx-2 transition-colors">
                    <span className="flex-1 text-left text-slate-700 capitalize truncate">{t.topic}</span>
                    <div className="w-16 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                      <div className={`h-full rounded-full ${t.mastery >= 0.5 ? 'bg-amber-400' : 'bg-red-400'}`} style={{ width: `${Math.round(t.mastery * 100)}%` }} />
                    </div>
                    <span className={`w-9 text-right font-semibold ${t.mastery >= 0.5 ? 'text-amber-600' : 'text-red-600'}`}>{Math.round(t.mastery * 100)}%</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Plan view */}
      {plan && (
        <>
          {/* Status header */}
          {plan.remaining_nodes === 0 ? (
            <div className="rounded-2xl border p-4 bg-amber-50 border-amber-200">
              <div className="flex items-center gap-2 font-semibold text-sm">
                <AlertTriangle size={16} className="text-amber-600" />
                <span className="text-amber-800">You haven't studied any {plan.subject} topics yet</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                Learn a few topics first — then this plan will schedule revision of what you've studied before the exam.
              </p>
            </div>
          ) : (
          <div className={`rounded-2xl border p-4 ${
            !plan.feasible ? 'bg-red-50 border-red-200'
              : plan.on_track ? 'bg-green-50 border-green-200' : 'bg-amber-50 border-amber-200'
          }`}>
            <div className="flex items-center gap-2 font-semibold text-sm">
              {!plan.feasible ? (
                <><AlertTriangle size={16} className="text-red-600" />
                  <span className="text-red-800">Not enough time to revise everything at {plan.daily_minutes} min/day — need ~{plan.required_daily_minutes} min/day</span></>
              ) : (
                <><CheckCircle2 size={16} className="text-green-600" />
                  <span className="text-green-800">Revision plan ready — {plan.days_to_exam} days to exam</span></>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Revising {plan.remaining_nodes} topic{plan.remaining_nodes !== 1 ? 's' : ''} you've studied · daily plan below
            </p>
          </div>
          )}

          {/* Today */}
          {plan.today_items?.length > 0 && (
            <div className="bg-brand-50 border border-brand-200 rounded-2xl p-4">
              <h3 className="font-semibold text-brand-800 text-sm mb-2">Today</h3>
              <div className="space-y-2">
                {plan.today_items.map((it, i) => {
                  const M = ITEM_META[it.type] || ITEM_META.learn;
                  const Icon = M.icon;
                  return (
                    <button key={i}
                      onClick={() => {
                        if (it.type === 'learn' || it.type === 'revise') navigate('/tutor', { state: { topic: it.title, subject: plan.subject } });
                        else if (it.type === 'mock_exam') navigate('/quiz');
                        else navigate('/session');
                      }}
                      className="w-full flex items-center gap-2 bg-white rounded-xl px-3 py-2 text-left hover:shadow-sm transition-all"
                    >
                      <Icon size={15} className={M.color} />
                      <span className="text-sm text-gray-800 flex-1">{it.title}</span>
                      <span className="text-xs text-gray-400">{it.est_minutes}m</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Full calendar */}
          <div className="bg-white border border-gray-200 rounded-2xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 text-sm">Day by day</h3>
              <button onClick={removePlan} className="text-gray-300 hover:text-red-500" title="Delete plan">
                <Trash2 size={15} />
              </button>
            </div>
            <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
              {plan.days.map((d, i) => {
                const isPast = d.date < plan.today;
                const isToday = d.date === plan.today;
                return (
                  <div key={i} className={`flex items-start gap-3 text-sm rounded-lg px-2 py-1.5 ${
                    isToday ? 'bg-brand-50' : ''
                  } ${isPast ? 'opacity-40' : ''}`}>
                    <span className="font-mono text-xs text-gray-400 w-14 flex-shrink-0 mt-0.5">
                      {d.date.slice(5)}
                    </span>
                    <div className="flex-1 space-y-0.5">
                      {d.items.map((it, j) => {
                        const M = ITEM_META[it.type] || ITEM_META.learn;
                        const Icon = M.icon;
                        return (
                          <div key={j} className="flex items-center gap-1.5 text-gray-700">
                            <Icon size={12} className={M.color} />
                            <span className="text-xs">{it.title}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
