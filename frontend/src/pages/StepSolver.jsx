import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import Markdown from '../components/Markdown';
import HandwritingCanvas from '../components/HandwritingCanvas';
import { useCelebration } from '../components/CelebrationManager';
import { ArrowLeft, Loader2, CheckCircle2, XCircle, Lightbulb, PenLine, Type, Sparkles, RotateCcw } from 'lucide-react';

/**
 * Feature #1: Live step-by-step solver.
 * The student writes ONE step at a time; each step is checked instantly.
 * Correct → it locks in and they move on. Wrong → a nudge, and they retry the
 * same step. Like a tutor watching over your shoulder.
 */
export default function StepSolver() {
  const navigate = useNavigate();
  const { celebrate } = useCelebration();
  const canvasRef = useRef(null);

  const [problem, setProblem] = useState('');
  const [topic, setTopic] = useState('');
  const [steps, setSteps] = useState([]);          // accepted steps: [{text}]
  const [inputMode, setInputMode] = useState('write'); // 'write' | 'type'
  const [stepText, setStepText] = useState('');
  const [result, setResult] = useState(null);      // last check result
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [solved, setSolved] = useState(false);

  const started = steps.length > 0;

  const checkStep = async () => {
    if (loading) return;
    if (!problem.trim()) { setError('Type the problem you\'re solving first.'); return; }
    setError('');

    const payload = { problem: problem.trim(), prevSteps: steps.map(s => s.text), topic: topic.trim() };
    if (inputMode === 'type') {
      if (!stepText.trim()) { setError('Write your step.'); return; }
      payload.stepText = stepText.trim();
    } else {
      if (canvasRef.current?.isBlank()) { setError('Write your step on the board.'); return; }
      const blob = await canvasRef.current?.getBlob();
      if (!blob) { setError('Could not read the board — try again.'); return; }
      payload.file = new File([blob], 'step.png', { type: 'image/png' });
    }

    setLoading(true);
    setResult(null);
    try {
      const r = await api.stepCheck(payload);
      setResult(r);
      if (r.correct) {
        setSteps(prev => [...prev, { text: r.transcription || stepText.trim() }]);
        setStepText('');
        canvasRef.current?.clear();
        if (r.is_final) {
          setSolved(true);
          try { celebrate([{ event: 'daily_goal_completed' }]); } catch { /* no-op */ }
        }
      }
    } catch (e) {
      setError(e.message || 'Step check failed');
    } finally {
      setLoading(false);
    }
  };

  const newProblem = () => {
    setProblem(''); setTopic(''); setSteps([]); setStepText('');
    setResult(null); setError(''); setSolved(false);
    canvasRef.current?.clear();
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-5 animate-fade-in">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/')} className="btn-ghost !px-2"><ArrowLeft size={20} /></button>
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Step-by-step solver</h2>
          <p className="text-xs text-slate-500">Solve one step at a time — I'll check each as you go</p>
        </div>
      </div>

      {/* Problem + topic */}
      <div className="space-y-2">
        <textarea
          className="input-field w-full text-sm resize-none"
          rows={2}
          placeholder="Type the problem, e.g. Solve 2x + 3 = 11"
          value={problem}
          onChange={e => setProblem(e.target.value)}
          disabled={started}
        />
        {!started && (
          <input className="input-field text-sm w-full" placeholder="Topic (optional, e.g. Algebra)"
            value={topic} onChange={e => setTopic(e.target.value)} />
        )}
      </div>

      {/* Accepted steps so far */}
      {steps.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Your working</p>
          {steps.map((s, i) => (
            <div key={i} className="flex items-start gap-2 bg-green-50 border border-green-200 rounded-xl px-3 py-2">
              <CheckCircle2 size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-slate-800 prose prose-sm max-w-none"><Markdown>{s.text}</Markdown></div>
            </div>
          ))}
        </div>
      )}

      {/* Solved banner */}
      {solved ? (
        <div className="rounded-2xl border border-green-200 bg-gradient-to-br from-green-50 to-emerald-50 p-5 text-center space-y-2">
          <Sparkles size={26} className="text-emerald-600 mx-auto" />
          <p className="font-bold text-emerald-800">Solved! Every step checks out. 🎉</p>
          <button onClick={newProblem} className="btn-primary mt-1"><RotateCcw size={16} /> New problem</button>
        </div>
      ) : (
        <>
          {/* Feedback / hint on the last attempt */}
          {result && (
            <div className={`rounded-xl border p-3 text-sm ${result.correct ? 'bg-green-50 border-green-200 text-green-800' : 'bg-amber-50 border-amber-200 text-amber-900'}`}>
              <div className="flex items-center gap-2 font-semibold">
                {result.correct
                  ? <><CheckCircle2 size={16} className="text-green-600" /> Nice — step accepted</>
                  : <><XCircle size={16} className="text-amber-600" /> Not quite — try this step again</>}
              </div>
              {result.feedback && <div className="mt-1"><Markdown>{result.feedback}</Markdown></div>}
              {!result.correct && result.hint && (
                <div className="mt-2 flex items-start gap-1.5 bg-white/70 rounded-lg p-2">
                  <Lightbulb size={14} className="text-amber-600 mt-0.5 flex-shrink-0" />
                  <div className="text-brand-800"><Markdown>{result.hint}</Markdown></div>
                </div>
              )}
            </div>
          )}

          {/* Input mode toggle */}
          <div className="flex gap-1 bg-slate-100 rounded-xl p-1">
            <button onClick={() => setInputMode('write')}
              className={`flex-1 flex items-center justify-center gap-1.5 text-sm font-medium py-2 rounded-lg transition-colors ${inputMode === 'write' ? 'bg-white shadow-sm text-brand-700' : 'text-slate-500'}`}>
              <PenLine size={16} /> Write step
            </button>
            <button onClick={() => setInputMode('type')}
              className={`flex-1 flex items-center justify-center gap-1.5 text-sm font-medium py-2 rounded-lg transition-colors ${inputMode === 'type' ? 'bg-white shadow-sm text-brand-700' : 'text-slate-500'}`}>
              <Type size={16} /> Type step
            </button>
          </div>

          {/* Step input */}
          {inputMode === 'write' ? (
            <HandwritingCanvas ref={canvasRef} height={240} />
          ) : (
            <input
              className="input-field w-full text-sm"
              placeholder={started ? 'Your next step…' : 'Your first step…'}
              value={stepText}
              onChange={e => setStepText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !loading) checkStep(); }}
            />
          )}

          {error && <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{error}</div>}

          <button onClick={checkStep} disabled={loading} className="btn-primary w-full">
            {loading ? <><Loader2 size={16} className="animate-spin" /> Checking…</> : <><CheckCircle2 size={16} /> Check this step</>}
          </button>

          {started && (
            <button onClick={newProblem} className="btn-ghost w-full text-sm text-slate-500">
              Start a different problem
            </button>
          )}
        </>
      )}
    </div>
  );
}
