import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import Markdown from '../components/Markdown';
import { ArrowLeft, Camera, Loader2, CheckCircle2, XCircle, RotateCcw, ImageUp, PenLine, Eraser, Trash2, Pencil } from 'lucide-react';

/**
 * Feature #1: Handwriting / whiteboard step-check.
 * The student WRITES their working on a canvas (or snaps a photo). A vision
 * model transcribes it, finds the FIRST wrong step and nudges the fix —
 * without handing over the full answer. Reuses the /me/solution-check backend.
 */
export default function SolutionCheck() {
  const navigate = useNavigate();
  const fileRef = useRef(null);
  const [mode, setMode] = useState('write'); // 'write' | 'photo'
  const [preview, setPreview] = useState(null);
  const [file, setFile] = useState(null);
  const [question, setQuestion] = useState('');
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  // ── Canvas drawing state ──
  const canvasRef = useRef(null);
  const drawing = useRef(false);
  const lastPt = useRef(null);
  const [tool, setTool] = useState('pen'); // 'pen' | 'eraser'
  const toolRef = useRef('pen');
  useEffect(() => { toolRef.current = tool; }, [tool]);

  // Paint a white background once the canvas mounts (so vision reads black-on-white)
  const paintWhite = () => {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, c.width, c.height);
  };
  useEffect(() => { if (mode === 'write') paintWhite(); }, [mode]);

  const getPos = (e) => {
    const c = canvasRef.current;
    const rect = c.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) * (c.width / rect.width),
      y: (e.clientY - rect.top) * (c.height / rect.height),
    };
  };
  const startDraw = (e) => { e.preventDefault(); drawing.current = true; lastPt.current = getPos(e); };
  const moveDraw = (e) => {
    if (!drawing.current) return;
    e.preventDefault();
    const ctx = canvasRef.current.getContext('2d');
    const p = getPos(e);
    ctx.strokeStyle = toolRef.current === 'eraser' ? '#ffffff' : '#111827';
    ctx.lineWidth = toolRef.current === 'eraser' ? 26 : 3.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(lastPt.current.x, lastPt.current.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    lastPt.current = p;
  };
  const endDraw = () => { drawing.current = false; lastPt.current = null; };
  const clearCanvas = () => { paintWhite(); setResult(null); setError(''); };

  const pick = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setResult(null);
    setError('');
    setPreview(URL.createObjectURL(f));
  };

  const runCheck = async (f) => {
    const img = f || file;
    if (!img || loading) return;
    setLoading(true); setError(''); setResult(null);
    try {
      setResult(await api.solutionCheck(img, question.trim(), topic.trim()));
    } catch (e) {
      setError(e.message || 'Failed to check');
    } finally { setLoading(false); }
  };

  // Export the canvas drawing to a PNG and run the step-check.
  const checkWriting = () => {
    const c = canvasRef.current;
    if (!c) return;
    c.toBlob((blob) => {
      if (!blob) { setError('Nothing to check yet — write your working first.'); return; }
      const f = new File([blob], 'handwriting.png', { type: 'image/png' });
      runCheck(f);
    }, 'image/png');
  };

  const reset = () => {
    setFile(null); setPreview(null); setResult(null); setError('');
    if (fileRef.current) fileRef.current.value = '';
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-5 animate-fade-in">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/')} className="btn-ghost !px-2"><ArrowLeft size={20} /></button>
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Check my solution</h2>
          <p className="text-xs text-slate-500">Write or snap your working — I'll find the first slip</p>
        </div>
      </div>

      {/* Mode toggle: write vs photo */}
      <div className="flex gap-1 bg-slate-100 rounded-xl p-1">
        <button onClick={() => { setMode('write'); reset(); }}
          className={`flex-1 flex items-center justify-center gap-1.5 text-sm font-medium py-2 rounded-lg transition-colors ${mode === 'write' ? 'bg-white shadow-sm text-brand-700' : 'text-slate-500'}`}>
          <PenLine size={16} /> Write it
        </button>
        <button onClick={() => { setMode('photo'); clearCanvas(); }}
          className={`flex-1 flex items-center justify-center gap-1.5 text-sm font-medium py-2 rounded-lg transition-colors ${mode === 'photo' ? 'bg-white shadow-sm text-brand-700' : 'text-slate-500'}`}>
          <Camera size={16} /> Photo
        </button>
      </div>

      {/* Optional context */}
      <div className="grid grid-cols-2 gap-2">
        <input className="input-field text-sm" placeholder="Topic (optional)" value={topic} onChange={e => setTopic(e.target.value)} />
        <input className="input-field text-sm" placeholder="Question (optional)" value={question} onChange={e => setQuestion(e.target.value)} />
      </div>

      {/* ── WRITE mode: handwriting canvas ── */}
      {mode === 'write' && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <button onClick={() => setTool('pen')}
              className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg ${tool === 'pen' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
              <Pencil size={14} /> Pen
            </button>
            <button onClick={() => setTool('eraser')}
              className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg ${tool === 'eraser' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
              <Eraser size={14} /> Eraser
            </button>
            <button onClick={clearCanvas}
              className="ml-auto flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 hover:bg-red-50 hover:text-red-600">
              <Trash2 size={14} /> Clear
            </button>
          </div>

          <div className="rounded-2xl overflow-hidden border-2 border-slate-200 shadow-soft bg-white">
            <canvas
              ref={canvasRef}
              width={760}
              height={460}
              onPointerDown={startDraw}
              onPointerMove={moveDraw}
              onPointerUp={endDraw}
              onPointerLeave={endDraw}
              className="w-full block cursor-crosshair"
              style={{ touchAction: 'none', aspectRatio: '760 / 460' }}
            />
          </div>
          <p className="text-xs text-slate-400 text-center">Write your steps like on paper. Use a stylus, finger, or mouse.</p>

          <button onClick={checkWriting} disabled={loading} className="btn-primary w-full">
            {loading ? <><Loader2 size={16} className="animate-spin" /> Reading your steps…</> : <><CheckCircle2 size={16} /> Check my working</>}
          </button>
        </div>
      )}

      {/* ── PHOTO mode ── */}
      {mode === 'photo' && (
        <>
          <input ref={fileRef} type="file" accept="image/*" capture="environment" onChange={pick} className="hidden" />
          {!preview ? (
            <button onClick={() => fileRef.current?.click()}
              className="w-full bg-gradient-to-br from-brand-50/60 to-white border-2 border-dashed border-brand-200 hover:border-brand-400 rounded-2xl p-10 flex flex-col items-center gap-3 text-slate-500 hover:text-brand-600 transition-all">
              <span className="w-14 h-14 rounded-2xl bg-white shadow-soft flex items-center justify-center"><Camera size={26} className="text-brand-500" /></span>
              <span className="text-sm font-semibold text-slate-700">Take a photo / upload your working</span>
              <span className="text-xs text-slate-400">Clear, well-lit · JPG or PNG</span>
            </button>
          ) : (
            <div className="space-y-3">
              <div className="rounded-2xl overflow-hidden border border-slate-200 shadow-soft">
                <img src={preview} alt="your solution" className="w-full object-contain max-h-80 bg-slate-50" />
              </div>
              <div className="flex gap-2">
                <button onClick={() => runCheck()} disabled={loading} className="btn-primary flex-1">
                  {loading ? <><Loader2 size={16} className="animate-spin" /> Reading your steps…</> : <><ImageUp size={16} /> Check this</>}
                </button>
                <button onClick={reset} className="btn-secondary"><RotateCcw size={16} /></button>
              </div>
            </div>
          )}
        </>
      )}

      {error && <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{error}</div>}

      {/* Result */}
      {result && (
        <div className="space-y-3 animate-scale-in">
          <div className={`rounded-2xl border p-4 ${result.has_error ? 'bg-amber-50 border-amber-200' : 'bg-green-50 border-green-200'}`}>
            <div className="flex items-center gap-2 font-bold text-sm">
              {result.has_error
                ? <><XCircle size={18} className="text-amber-600" /><span className="text-amber-800">Found a slip</span></>
                : <><CheckCircle2 size={18} className="text-green-600" /><span className="text-green-800">Looks correct!</span></>}
            </div>
            {result.has_error && (
              <div className="mt-2 text-sm text-amber-900">
                <p><span className="font-semibold">Where:</span> {result.first_error_step}</p>
                <div className="mt-1"><span className="font-semibold">Why:</span> <Markdown>{result.why_wrong || ''}</Markdown></div>
                {result.hint_to_fix && <div className="mt-2 bg-white/70 rounded-lg p-2 text-brand-800"><span className="font-semibold">Nudge:</span> <Markdown>{result.hint_to_fix}</Markdown></div>}
              </div>
            )}
          </div>

          {result.transcription && (
            <details className="card-tight text-sm">
              <summary className="cursor-pointer font-semibold text-slate-700">What I read from your working</summary>
              <div className="mt-2 prose prose-sm max-w-none"><Markdown>{result.transcription}</Markdown></div>
            </details>
          )}

          {result.has_error && (
            <button onClick={() => navigate('/ask', { state: { prefill: `I made an error here: ${result.first_error_step}. ${result.why_wrong} Help me fix it.` } })}
              className="btn-secondary w-full">Work through the fix with the tutor</button>
          )}
        </div>
      )}
    </div>
  );
}
