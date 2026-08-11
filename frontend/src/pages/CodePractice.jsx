import { useState, useRef, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { ArrowLeft, Play, Loader2, CheckCircle, XCircle, Sparkles } from 'lucide-react';

/**
 * A4: In-browser Python practice.
 * Code runs CLIENT-SIDE in Pyodide inside a Web Worker (terminated on 15s timeout)
 * — the server never executes student code. Test results go to /code-feedback
 * for Socratic AI feedback (never the solution).
 */

const DEFAULT_EXERCISE = {
  question: 'Write a function `total(nums)` that returns the sum of a list of numbers. An empty list returns 0.',
  starter_code: 'def total(nums):\n    # your code here\n    pass\n',
  tests: [
    { name: 'sums numbers', code: 'assert total([1, 2, 3]) == 6' },
    { name: 'empty list is 0', code: 'assert total([]) == 0' },
    { name: 'handles negatives', code: 'assert total([-1, 1, 5]) == 5' },
  ],
};

const WORKER_SOURCE = `
  importScripts('https://cdn.jsdelivr.net/pyodide/v0.25.1/full/pyodide.js');
  let pyodideReady = loadPyodide();
  self.onmessage = async (e) => {
    const { code, tests } = e.data;
    try {
      const pyodide = await pyodideReady;
      let results = [];
      // Run the student's code
      try {
        await pyodide.runPythonAsync(code);
      } catch (err) {
        self.postMessage({ error: String(err).slice(0, 500), results: [] });
        return;
      }
      // Run each test
      for (const t of tests) {
        try {
          await pyodide.runPythonAsync(t.code);
          results.push({ name: t.name, passed: true, output: '' });
        } catch (err) {
          results.push({ name: t.name, passed: false, output: String(err).slice(0, 300) });
        }
      }
      self.postMessage({ error: null, results });
    } catch (err) {
      self.postMessage({ error: 'Runtime failed to load: ' + String(err).slice(0, 200), results: [] });
    }
  };
`;

export default function CodePractice() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const topic = params.get('topic') || 'Python Programming';

  const [exercise] = useState(DEFAULT_EXERCISE);
  const [code, setCode] = useState(DEFAULT_EXERCISE.starter_code);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState('');
  const [results, setResults] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const workerRef = useRef(null);

  useEffect(() => () => workerRef.current?.terminate(), []);

  const runCode = () => {
    if (running) return;
    setRunning(true);
    setRunError('');
    setResults(null);
    setFeedback(null);

    const blob = new Blob([WORKER_SOURCE], { type: 'application/javascript' });
    const worker = new Worker(URL.createObjectURL(blob));
    workerRef.current = worker;

    const timeout = setTimeout(() => {
      worker.terminate();
      setRunning(false);
      setRunError('Execution timed out (15s) — check for infinite loops.');
    }, 15000);

    worker.onmessage = (e) => {
      clearTimeout(timeout);
      worker.terminate();
      setRunning(false);
      if (e.data.error) setRunError(e.data.error);
      setResults(e.data.results || []);
    };
    worker.onerror = () => {
      clearTimeout(timeout);
      worker.terminate();
      setRunning(false);
      setRunError('Could not start the Python runtime — check your connection.');
    };
    worker.postMessage({ code, tests: exercise.tests });
  };

  const getFeedback = async () => {
    if (feedbackLoading || !results) return;
    setFeedbackLoading(true);
    try {
      const fb = await api.codeFeedback({
        question: exercise.question,
        code,
        test_results: results,
        topic,
      });
      setFeedback(fb);
    } catch (err) {
      setFeedback({ feedback: `Error: ${err.message}`, guiding_question: '' });
    } finally {
      setFeedbackLoading(false);
    }
  };

  const passedCount = results?.filter(r => r.passed).length ?? 0;
  const allPassed = results && passedCount === results.length && results.length > 0;

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={20} />
        </button>
        <div>
          <h2 className="text-xl font-bold text-gray-900">Code practice</h2>
          <p className="text-xs text-gray-500">{topic} · runs in your browser, nothing installed</p>
        </div>
      </div>

      {/* Exercise */}
      <div className="bg-brand-50 border border-brand-100 rounded-2xl p-4">
        <p className="text-sm text-brand-900 font-medium">{exercise.question}</p>
      </div>

      {/* Editor */}
      <div className="bg-gray-900 rounded-2xl overflow-hidden">
        <textarea
          className="w-full min-h-[220px] bg-gray-900 text-gray-100 font-mono text-sm p-4 outline-none resize-y"
          spellCheck={false}
          value={code}
          onChange={e => setCode(e.target.value)}
        />
      </div>

      <div className="flex gap-3">
        <button onClick={runCode} disabled={running} className="btn-primary flex items-center gap-2 disabled:opacity-50">
          {running ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {running ? 'Running…' : 'Run tests'}
        </button>
        {results && !allPassed && (
          <button onClick={getFeedback} disabled={feedbackLoading} className="btn-secondary flex items-center gap-2 disabled:opacity-50">
            {feedbackLoading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            Get a hint from your tutor
          </button>
        )}
      </div>

      {runError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-800 font-mono whitespace-pre-wrap">
          {runError}
        </div>
      )}

      {/* Test results */}
      {results && (
        <div className="bg-white border border-gray-200 rounded-2xl p-4 space-y-2">
          <p className="text-sm font-semibold text-gray-800">
            Tests: {passedCount}/{results.length} passing {allPassed && '🎉'}
          </p>
          {results.map((r, i) => (
            <div key={i} className={`flex items-start gap-2 text-sm rounded-lg px-3 py-2 ${r.passed ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
              {r.passed ? <CheckCircle size={15} className="mt-0.5 flex-shrink-0" /> : <XCircle size={15} className="mt-0.5 flex-shrink-0" />}
              <div>
                <span className="font-medium">{r.name}</span>
                {!r.passed && r.output && <p className="text-xs font-mono mt-0.5 opacity-80">{r.output}</p>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* AI feedback */}
      {feedback && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 space-y-2">
          <p className="text-sm text-amber-900">{feedback.feedback}</p>
          {feedback.guiding_question && (
            <p className="text-sm text-amber-800 font-medium">🤔 {feedback.guiding_question}</p>
          )}
          {feedback.concept_hint && (
            <p className="text-xs text-amber-700">Concept: {feedback.concept_hint}</p>
          )}
        </div>
      )}
    </div>
  );
}
