import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, ArrowRight, RotateCcw, Trophy, Target, BookOpen, Lightbulb, RefreshCw, TimerIcon, Flag } from 'lucide-react';
import { api } from '../lib/api';

/**
 * Shared quiz UI component used by both in-chat and standalone quiz.
 * Props:
 *   quiz: { quiz_title, questions: [...], quiz_id }   (questions may be MCQ or type "open")
 *   onSubmit: async (quiz_id, answers) => scoreResult
 *   onHint: async (quiz_id, questionId, hintNumber) => { hint, hints_used, exhausted }  (optional)
 *   onRetryWrong: async (quiz_id) => newQuizPayload  (optional)
 *   onRetake: () => void  (optional — start a brand new quiz)
 *   onDone: () => void     (optional — leave the results screen / exit quiz mode)
 *   compact: bool (for in-chat mode)
 */
export default function QuizView({ quiz, onSubmit, onHint, onRetryWrong, onRetake, onDone, onPracticeTopic, compact = false }) {
  const [activeQuiz, setActiveQuiz] = useState(quiz);
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [results, setResults] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [hints, setHints] = useState({}); // { [qid]: { list: [str], loading: bool, exhausted: bool } }
  const [timeLeft, setTimeLeft] = useState(null); // B1: exam countdown (seconds)
  const [reported, setReported] = useState({}); // B2: { [qid]: true }

  // B2: flag a bad question from the review screen
  const reportQuestion = async (r) => {
    if (reported[r.id]) return;
    setReported(prev => ({ ...prev, [r.id]: true }));
    try {
      await api.reportQuestion({
        quiz_id: activeQuiz?.quiz_id,
        question_id: r.id,
        question: r.question,
        concept: r.concept || '',
        topic: activeQuiz?.quiz_title || '',
        reason: 'flagged by student from result review',
      });
    } catch { /* keep optimistic state */ }
  };

  // Load a quiz (from prop or from retry-wrong) and reset all attempt state
  const loadQuiz = (qz) => {
    setActiveQuiz(qz);
    setCurrentQ(0);
    setAnswers({});
    setSubmitted(false);
    setResults(null);
    setHints({});
  };

  // When the parent passes a new quiz object, reset to it
  useEffect(() => { loadQuiz(quiz); /* eslint-disable-next-line */ }, [quiz?.quiz_id]);

  // B1: exam timer — counts down to the server deadline, auto-submits at 0
  const isExam = activeQuiz?.mode === 'exam';
  useEffect(() => {
    if (!isExam || submitted || !activeQuiz) return;
    const deadlineMs = activeQuiz.deadline
      ? activeQuiz.deadline * 1000
      : Date.now() + (activeQuiz.duration_minutes || 15) * 60000;
    const tick = () => {
      const left = Math.max(0, Math.floor((deadlineMs - Date.now()) / 1000));
      setTimeLeft(left);
      if (left <= 0) handleSubmit();
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
    // eslint-disable-next-line
  }, [activeQuiz?.quiz_id, isExam, submitted]);

  if (!activeQuiz?.questions?.length) return null;

  const questions = activeQuiz.questions;
  const q = questions[currentQ];
  const isOpen = q.type === 'open';
  const selected = answers[q.id] || [];

  const toggleOption = (opt) => {
    if (submitted) return;
    const current = [...selected];
    if (q.multiple) {
      const idx = current.indexOf(opt);
      if (idx >= 0) current.splice(idx, 1);
      else current.push(opt);
    } else {
      current.length = 0;
      current.push(opt);
    }
    setAnswers({ ...answers, [q.id]: current });
  };

  const setOpenText = (val) => {
    if (submitted) return;
    setAnswers({ ...answers, [q.id]: val.trim() ? [val] : [] });
  };

  const requestHint = async () => {
    if (!onHint) return;
    const h = hints[q.id] || { list: [], loading: false, exhausted: false };
    if (h.exhausted || h.list.length >= 3 || h.loading) return;
    setHints({ ...hints, [q.id]: { ...h, loading: true } });
    try {
      const res = await onHint(activeQuiz.quiz_id, q.id, h.list.length + 1);
      setHints((prev) => {
        const cur = prev[q.id] || { list: [] };
        return {
          ...prev,
          [q.id]: {
            list: res?.hint ? [...cur.list, res.hint] : cur.list,
            loading: false,
            exhausted: !!res?.exhausted || (cur.list.length + 1) >= 3,
          },
        };
      });
    } catch {
      setHints((prev) => ({ ...prev, [q.id]: { ...(prev[q.id] || { list: [] }), loading: false } }));
    }
  };

  const handleSubmit = async () => {
    if (submitting || submitted) return;
    setSubmitting(true);
    try {
      const res = await onSubmit(activeQuiz.quiz_id, answers);
      setResults(res);
      setSubmitted(true);
    } catch (err) {
      alert(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetryWrong = async () => {
    if (!onRetryWrong) return;
    setRetrying(true);
    try {
      const newQuiz = await onRetryWrong(activeQuiz.quiz_id);
      if (newQuiz?.questions?.length) loadQuiz(newQuiz);
    } catch (err) {
      alert(err.message);
    } finally {
      setRetrying(false);
    }
  };

  const answeredCount = Object.keys(answers).filter(k => answers[k]?.length > 0).length;
  const allAnswered = answeredCount === questions.length;

  // ─── Results view ───
  if (submitted && results) {
    const pct = results.score_percentage;
    const grade = pct >= 90 ? 'A+' : pct >= 80 ? 'A' : pct >= 70 ? 'B' : pct >= 60 ? 'C' : pct >= 50 ? 'D' : 'F';
    const gradeColor = pct >= 70 ? 'text-green-600' : pct >= 50 ? 'text-amber-600' : 'text-red-600';

    return (
      <div className={compact ? '' : 'max-w-3xl mx-auto'}>
        {/* Score banner */}
        <div className={`rounded-2xl p-8 mb-6 text-center relative overflow-hidden ${
          results.passed ? 'bg-gradient-to-br from-green-50 to-emerald-50 border border-green-200' : 'bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200'
        }`}>
          {results.mode === 'exam' && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700 uppercase tracking-wide">
              Exam result{results.late_submission ? ' · submitted late' : ''}
            </span>
          )}
          <div className="flex items-center justify-center gap-3 mb-3 mt-1">
            <Trophy size={28} className={results.passed ? 'text-green-500' : 'text-amber-500'} />
            <span className={`text-5xl font-extrabold ${gradeColor}`}>{grade}</span>
          </div>
          <p className="text-3xl font-bold text-gray-900 mb-1">{pct}%</p>
          <p className="text-lg font-medium text-gray-700">{results.correct_count} / {results.total_questions} correct</p>
          <p className={`text-sm mt-2 font-medium ${results.passed ? 'text-green-700' : 'text-amber-700'}`}>
            {pct >= 90 ? 'Outstanding! You nailed it!' :
             pct >= 70 ? 'Great job! You passed!' :
             pct >= 50 ? 'Good effort — review the explanations below to improve.' :
             'Keep practicing — read through the explanations to strengthen your understanding.'}
          </p>

          {/* Stats row */}
          <div className="flex justify-center gap-6 mt-4 text-sm">
            <div className="flex items-center gap-1.5">
              <CheckCircle size={14} className="text-green-500" />
              <span className="text-gray-600">{results.correct_count} correct</span>
            </div>
            <div className="flex items-center gap-1.5">
              <XCircle size={14} className="text-red-500" />
              <span className="text-gray-600">{results.total_questions - results.correct_count} wrong</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Target size={14} className="text-brand-500" />
              <span className="text-gray-600">{results.total_questions} total</span>
            </div>
          </div>
        </div>

        {/* C2: Per-topic score breakdown (mock tests span multiple concepts) */}
        {(() => {
          const byConcept = {};
          (results.results || []).forEach(r => {
            const c = r.concept || 'General';
            byConcept[c] = byConcept[c] || { correct: 0, total: 0 };
            byConcept[c].total += 1;
            if (r.is_correct) byConcept[c].correct += 1;
          });
          const topics = Object.entries(byConcept);
          if (topics.length < 2) return null; // single-topic quiz — skip
          return (
            <div className="bg-white border border-gray-200 rounded-2xl p-4 mb-6">
              <h3 className="font-semibold text-gray-900 text-sm mb-3 flex items-center gap-2">
                <Target size={16} className="text-brand-500" /> Where you bled marks
              </h3>
              <div className="space-y-2">
                {topics.sort((a, b) => (a[1].correct / a[1].total) - (b[1].correct / b[1].total)).map(([c, s]) => {
                  const p = Math.round((s.correct / s.total) * 100);
                  return (
                    <div key={c} className="flex items-center gap-3 text-sm">
                      <span className="flex-1 truncate text-gray-700 capitalize">{c}</span>
                      <div className="w-24 h-2 rounded-full bg-gray-100 overflow-hidden">
                        <div className={`h-full rounded-full ${p >= 70 ? 'bg-green-500' : p >= 40 ? 'bg-amber-500' : 'bg-red-500'}`}
                          style={{ width: `${p}%` }} />
                      </div>
                      <span className={`w-10 text-right font-semibold ${p >= 70 ? 'text-green-600' : p >= 40 ? 'text-amber-600' : 'text-red-600'}`}>{p}%</span>
                      {onPracticeTopic && p < 70 && (
                        <button onClick={() => onPracticeTopic(c)} className="text-xs text-brand-600 hover:underline">practice</button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })()}

        {/* Section header */}
        <div className="flex items-center gap-2 mb-4">
          <BookOpen size={18} className="text-brand-600" />
          <h3 className="font-semibold text-gray-900">Question Review & Explanations</h3>
        </div>

        {/* Per-question review — ALL questions with explanations */}
        <div className="space-y-4">
          {results.results.map((r, idx) => {
            // Find the original question to get the options text
            const origQ = questions.find(oq => oq.id === r.id);
            const optionsMap = origQ?.options || {};

            return (
              <div key={r.id} className={`rounded-xl border-2 overflow-hidden ${
                r.is_correct ? 'border-green-200' : 'border-red-200'
              }`}>
                {/* Question header */}
                <div className={`px-4 py-3 flex items-start gap-3 ${
                  r.is_correct ? 'bg-green-50' : 'bg-red-50'
                }`}>
                  <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 ${
                    r.is_correct ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
                  }`}>{idx + 1}</span>
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-gray-900">{r.question}</p>
                    {r.concept && (
                      <span className="text-xs text-gray-500 mt-0.5 inline-block">Concept: {r.concept}</span>
                    )}
                  </div>
                  <button
                    onClick={() => reportQuestion(r)}
                    disabled={reported[r.id]}
                    className={`flex-shrink-0 mt-0.5 transition-colors ${
                      reported[r.id] ? 'text-orange-400' : 'text-gray-300 hover:text-orange-500'
                    }`}
                    title={reported[r.id] ? 'Reported — thanks!' : 'Report a problem with this question'}
                  >
                    <Flag size={15} />
                  </button>
                  {r.is_correct
                    ? <CheckCircle size={20} className="text-green-500 flex-shrink-0 mt-0.5" />
                    : <XCircle size={20} className="text-red-500 flex-shrink-0 mt-0.5" />}
                </div>

                {/* Open-ended answer review */}
                {r.type === 'open' ? (
                  <div className="px-4 py-3 space-y-2">
                    <div className={`px-3 py-2 rounded-lg border text-sm ${
                      r.is_correct ? 'bg-green-50 border-green-300 text-green-800' : 'bg-red-50 border-red-300 text-red-800'
                    }`}>
                      <span className="text-xs font-semibold opacity-70">Your answer: </span>
                      {r.user_answer || <em className="opacity-60">（no answer）</em>}
                    </div>
                    {!r.is_correct && r.correct_answer && (
                      <div className="px-3 py-2 rounded-lg border bg-green-50 border-green-300 text-green-800 text-sm">
                        <span className="text-xs font-semibold opacity-70">Correct answer: </span>
                        {r.correct_answer}
                      </div>
                    )}
                    {r.misconception && (
                      <p className="text-xs text-amber-700"><span className="font-semibold">Misconception: </span>{r.misconception}</p>
                    )}
                  </div>
                ) : (
                <div className="px-4 py-3 space-y-1.5">
                  {Object.entries(optionsMap).map(([key, text]) => {
                    const isCorrect = r.correct.includes(key);
                    const wasSelected = r.submitted.includes(key);
                    let optClass = 'bg-white border-gray-200 text-gray-600';
                    let badge = null;

                    if (isCorrect && wasSelected) {
                      optClass = 'bg-green-50 border-green-300 text-green-800';
                      badge = <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-medium">Correct</span>;
                    } else if (isCorrect && !wasSelected) {
                      optClass = 'bg-green-50 border-green-300 text-green-800';
                      badge = <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-medium">Correct answer</span>;
                    } else if (!isCorrect && wasSelected) {
                      optClass = 'bg-red-50 border-red-300 text-red-800 line-through';
                      badge = <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-medium">Your pick</span>;
                    }

                    return (
                      <div key={key} className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${optClass}`}>
                        <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                          isCorrect ? 'bg-green-500 text-white' : wasSelected ? 'bg-red-400 text-white' : 'bg-gray-100 text-gray-400'
                        }`}>{key}</span>
                        <span className="flex-1">{text}</span>
                        {badge}
                      </div>
                    );
                  })}
                </div>
                )}

                {/* Explanation — always shown */}
                {r.explanation && (
                  <div className="px-4 pb-4">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                      <p className="text-xs font-semibold text-blue-700 mb-1 flex items-center gap-1">
                        <BookOpen size={12} /> Explanation
                      </p>
                      <p className="text-sm text-blue-900">{r.explanation}</p>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Results actions */}
        {(() => {
          const wrongCount = (results.results || []).filter(r => !r.is_correct).length;
          return (
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              {onRetryWrong && wrongCount > 0 && (
                <button
                  onClick={handleRetryWrong}
                  disabled={retrying}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50"
                >
                  <RefreshCw size={16} className={retrying ? 'animate-spin' : ''} />
                  {retrying ? 'Loading...' : `Retry wrong questions (${wrongCount})`}
                </button>
              )}
              {onRetake && (
                <button onClick={onRetake} className="btn-secondary flex items-center gap-2">
                  <RotateCcw size={16} /> Take Another Quiz
                </button>
              )}
              {onDone && (
                <button onClick={onDone} className="btn-secondary flex items-center gap-2">
                  Done
                </button>
              )}
            </div>
          );
        })()}
      </div>
    );
  }

  // ─── Quiz in progress ───
  return (
    <div className={compact ? '' : 'max-w-3xl mx-auto'}>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2 min-w-0">
          <span className="truncate">{activeQuiz.quiz_title}</span>
          {isExam && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700 uppercase tracking-wide flex-shrink-0">Exam</span>
          )}
        </h3>
        <div className="flex items-center gap-3 flex-shrink-0">
          {isExam && timeLeft !== null && (
            <span className={`flex items-center gap-1 text-sm font-mono font-semibold px-2.5 py-1 rounded-lg ${
              timeLeft <= 60 ? 'bg-red-100 text-red-700 animate-pulse' : 'bg-gray-100 text-gray-700'
            }`}>
              <TimerIcon size={14} />
              {Math.floor(timeLeft / 60)}:{String(timeLeft % 60).padStart(2, '0')}
            </span>
          )}
          <span className="text-sm text-gray-500">{answeredCount}/{questions.length} answered</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="bg-gray-100 rounded-full h-2 mb-6 overflow-hidden">
        <div
          className="h-full bg-brand-500 rounded-full transition-all duration-300"
          style={{ width: `${(answeredCount / questions.length) * 100}%` }}
        />
      </div>

      {/* Question */}
      <div className="card mb-4">
        <div className="flex items-center gap-3 mb-4">
          <span className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-sm font-bold">
            {currentQ + 1}
          </span>
          <div className="flex-1">
            <p className="font-medium text-gray-900">{q.question}</p>
            {q.multiple && (
              <p className="text-xs text-amber-600 mt-1">Select all that apply</p>
            )}
          </div>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            q.difficulty === 'easy' ? 'bg-green-100 text-green-700' :
            q.difficulty === 'hard' ? 'bg-red-100 text-red-700' :
            'bg-blue-100 text-blue-700'
          }`}>{q.difficulty}</span>
        </div>

        {/* Answer area — open (free text) or MCQ (options) */}
        {isOpen ? (
          <textarea
            className="input-field w-full min-h-[100px] resize-y"
            placeholder="Type your answer..."
            value={selected[0] || ''}
            onChange={(e) => setOpenText(e.target.value)}
          />
        ) : (
          <div className="space-y-2">
            {Object.entries(q.options).map(([key, text]) => {
              const isSelected = selected.includes(key);
              return (
                <button
                  key={key}
                  onClick={() => toggleOption(key)}
                  className={`w-full text-left px-4 py-3 rounded-xl border-2 transition-all text-sm flex items-center gap-3 ${
                    isSelected
                      ? 'border-brand-500 bg-brand-50 text-brand-900'
                      : 'border-gray-200 hover:border-gray-300 text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <span className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                    isSelected ? 'bg-brand-500 text-white' : 'bg-gray-100 text-gray-500'
                  }`}>{key}</span>
                  {text}
                </button>
              );
            })}
          </div>
        )}

        {/* Per-question hints — practice mode only (B1: no hints in exams) */}
        {onHint && !isExam && (
          <div className="mt-4 border-t border-gray-100 pt-3">
            <button
              onClick={requestHint}
              disabled={(hints[q.id]?.list.length || 0) >= 3 || hints[q.id]?.loading}
              className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-40"
            >
              <Lightbulb size={14} />
              {hints[q.id]?.loading ? 'Getting hint...'
                : (hints[q.id]?.list.length || 0) >= 3 ? 'No more hints'
                : `Hint (${hints[q.id]?.list.length || 0}/3)`}
            </button>
            {hints[q.id]?.list.map((h, i) => (
              <div key={i} className="mt-2 bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-sm text-amber-900">
                <span className="font-semibold text-amber-700">Hint {i + 1}: </span>{h}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          onClick={() => setCurrentQ(Math.max(0, currentQ - 1))}
          disabled={currentQ === 0}
          className="btn-secondary text-sm disabled:opacity-30 flex-shrink-0"
        >
          Previous
        </button>

        <div className="flex flex-wrap justify-center gap-1 order-last w-full sm:order-none sm:w-auto">
          {questions.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrentQ(i)}
              className={`w-7 h-7 rounded-full text-xs font-medium transition-colors ${
                i === currentQ
                  ? 'bg-brand-500 text-white'
                  : answers[questions[i].id]?.length
                    ? 'bg-brand-100 text-brand-700'
                    : 'bg-gray-100 text-gray-400'
              }`}
            >
              {i + 1}
            </button>
          ))}
        </div>

        {currentQ < questions.length - 1 ? (
          <button
            onClick={() => setCurrentQ(currentQ + 1)}
            className="btn-secondary text-sm flex items-center gap-1"
          >
            Next <ArrowRight size={14} />
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={(!allAnswered && !isExam) || submitting}
            className="btn-primary text-sm disabled:opacity-50"
          >
            {submitting ? 'Scoring...' : isExam ? 'Submit Exam' : 'Submit Quiz'}
          </button>
        )}
      </div>
    </div>
  );
}
