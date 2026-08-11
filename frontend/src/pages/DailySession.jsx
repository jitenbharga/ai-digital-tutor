import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { ArrowLeft, ArrowRight, RefreshCw, Sparkles, Zap, CheckCircle2, PartyPopper } from 'lucide-react';

const STEP_META = {
  review:        { icon: RefreshCw, color: 'text-amber-600', bg: 'bg-amber-50', label: 'Review',   go: '/review' },
  continue:      { icon: Sparkles,  color: 'text-brand-600', bg: 'bg-brand-50', label: 'Continue', go: '/tutor' },
  mistake_retry: { icon: Zap,       color: 'text-red-500',   bg: 'bg-red-50',   label: 'Retry',    go: '/mistakes' },
};

/**
 * A2: One-tap Daily Session player.
 * Fetches a composed playlist (reviews due + continue point + mistake retries)
 * and walks the student through it step by step with a progress bar.
 */
export default function DailySession() {
  const navigate = useNavigate();
  const [session, setSession] = useState(null);
  const [step, setStep] = useState(0);
  const [doneSteps, setDoneSteps] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.dailySession()
      .then(s => { setSession(s); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <div className="animate-spin h-8 w-8 border-4 border-brand-500 border-t-transparent rounded-full" />
        <p className="text-sm text-gray-500">Building your session…</p>
      </div>
    );
  }

  if (!session || session.empty) {
    return (
      <div className="max-w-lg mx-auto px-4 py-10 text-center space-y-4">
        <p className="text-gray-600">Nothing queued yet — pick a subject to get started!</p>
        <button onClick={() => navigate('/learn')} className="btn-primary">Choose a topic</button>
      </div>
    );
  }

  const playlist = session.playlist;
  const completedCount = Object.keys(doneSteps).length;
  const allDone = completedCount >= playlist.length;

  const markDone = (i) => {
    setDoneSteps(prev => ({ ...prev, [i]: true }));
    if (i === step && step < playlist.length - 1) setStep(step + 1);
  };

  const startItem = (item) => {
    const meta = STEP_META[item.type] || STEP_META.continue;
    if (item.type === 'continue') navigate('/tutor', { state: { topic: item.topic } });
    else navigate(meta.go);
  };

  // ── Summary screen ──
  if (allDone) {
    return (
      <div className="max-w-lg mx-auto px-4 py-10 text-center space-y-4">
        <PartyPopper size={40} className="text-brand-500 mx-auto" />
        <h2 className="text-2xl font-bold text-gray-900">Session complete!</h2>
        <p className="text-gray-500 text-sm">
          {playlist.length} step{playlist.length > 1 ? 's' : ''} done · ~{session.est_minutes} min of focused learning.
          Same time tomorrow?
        </p>
        <button onClick={() => navigate('/')} className="btn-primary">Back home</button>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/')} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={20} />
        </button>
        <div>
          <h2 className="text-xl font-bold text-gray-900">Today's session</h2>
          <p className="text-xs text-gray-500">~{session.est_minutes} min · {playlist.length} steps</p>
        </div>
        <span className="ml-auto text-sm font-semibold text-brand-600">{completedCount}/{playlist.length}</span>
      </div>

      {/* Progress bar */}
      <div className="bg-gray-100 rounded-full h-2 overflow-hidden">
        <div className="h-full bg-brand-500 rounded-full transition-all duration-300"
          style={{ width: `${(completedCount / playlist.length) * 100}%` }} />
      </div>

      {/* Steps */}
      <div className="space-y-3">
        {playlist.map((item, i) => {
          const meta = STEP_META[item.type] || STEP_META.continue;
          const Icon = meta.icon;
          const done = !!doneSteps[i];
          const active = i === step && !done;
          return (
            <div key={i} className={`rounded-2xl border p-4 transition-all ${
              done ? 'bg-green-50 border-green-200 opacity-70'
                : active ? 'bg-white border-brand-300 shadow-sm'
                : 'bg-white border-gray-200'
            }`}>
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${done ? 'bg-green-100' : meta.bg}`}>
                  {done ? <CheckCircle2 size={20} className="text-green-500" /> : <Icon size={20} className={meta.color} />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`font-semibold text-sm ${done ? 'text-green-700 line-through' : 'text-gray-900'}`}>
                    {meta.label}: <span className="capitalize">{item.topic || item.concept || ''}</span>
                  </p>
                  <p className="text-xs text-gray-400 truncate">
                    {item.type === 'review' && `Recall dropping (${Math.round((item.retention || 0) * 100)}%) — quick refresh`}
                    {item.type === 'continue' && 'Pick up where you left off'}
                    {item.type === 'mistake_retry' && (item.question || 'Retry a missed question')}
                  </p>
                </div>
                {!done && (
                  <div className="flex gap-2 flex-shrink-0">
                    <button onClick={() => startItem(item)} className="btn-primary text-xs px-3 py-2 flex items-center gap-1">
                      Start <ArrowRight size={12} />
                    </button>
                    <button onClick={() => markDone(i)} className="btn-secondary text-xs px-3 py-2" title="Mark step complete">
                      ✓
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-[11px] text-gray-400 text-center">
        Do a step, come back, tick it ✓ — finish all for today's win.
      </p>
    </div>
  );
}
