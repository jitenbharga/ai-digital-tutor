import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import QuizView from '../components/QuizView';
import { ClipboardList, BookOpen, Sparkles, Timer, Target } from 'lucide-react';

const PRESET_TOPICS = [
  'Algebra', 'Calculus', 'Physics', 'Chemistry',
  'Biology', 'Computer Science', 'Literature', 'History',
];

export default function QuizPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const studentId = user?.username || 'anon';
  const [phase, setPhase] = useState('select'); // select | loading | quiz
  const [selectedTopic, setSelectedTopic] = useState('');
  const [customTopic, setCustomTopic] = useState('');
  const [studiedTopics, setStudiedTopics] = useState([]);
  const [quiz, setQuiz] = useState(null);
  const [error, setError] = useState('');
  const [mode, setMode] = useState('practice'); // B1: practice | exam
  const [duration, setDuration] = useState(15); // exam minutes

  // Load studied topics from knowledge graph
  useEffect(() => {
    api.knowledgeGraph(studentId)
      .then(data => {
        if (data?.nodes) {
          setStudiedTopics(data.nodes.map(n => n.topic));
        }
      })
      .catch(() => {});
  }, [studentId]);

  // S1: a quiz handed over from the Materials page (via router state)
  useEffect(() => {
    if (location.state?.quiz?.quiz_id) {
      setQuiz(location.state.quiz);
      setPhase('quiz');
      navigate('.', { replace: true, state: {} }); // clear so refresh doesn't re-trigger
    }
  }, [location.state]); // eslint-disable-line

  const startQuiz = async (topic) => {
    setPhase('loading');
    setError('');
    try {
      const data = await api.generateQuiz(studentId, topic, 10, mode, duration);
      setQuiz(data);
      setPhase('quiz');
    } catch (err) {
      setError(err.message);
      setPhase('select');
    }
  };

  const handleSubmit = async (quizId, answers) => {
    return await api.submitQuiz(studentId, quizId, answers);
  };

  const handleHint = async (quizId, questionId, hintNumber) => {
    return await api.quizHint(quizId, questionId, hintNumber);
  };

  const handleRetake = () => {
    setQuiz(null);
    setPhase('select');
  };

  // C2: full-syllabus weighted mock
  const startMock = async (subject) => {
    setPhase('loading');
    setError('');
    try {
      const data = await api.mockTest(subject, 15, 20);
      setQuiz(data);
      setPhase('quiz');
    } catch (err) {
      setError(err.message);
      setPhase('select');
    }
  };

  // One-tap targeted practice from the student's own weak areas.
  const startWeakSpots = async () => {
    setPhase('loading');
    setError('');
    try {
      const data = await api.practiceWeakSpots(8);
      if (data.empty) {
        setError(data.message || 'No weak spots yet — do a few quizzes first.');
        setPhase('select');
        return;
      }
      setQuiz(data);
      setPhase('quiz');
    } catch (err) {
      setError(err.message);
      setPhase('select');
    }
  };

  const practiceTopic = (topicName) => {
    navigate('/tutor', { state: { topic: topicName } });
  };

  // Loading state
  if (phase === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center h-72 gap-4 animate-fade-in">
        <div className="relative">
          <div className="animate-spin h-12 w-12 border-4 border-brand-100 border-t-brand-600 rounded-full" />
          <ClipboardList size={18} className="text-brand-600 absolute inset-0 m-auto" />
        </div>
        <p className="text-ink-muted text-sm font-medium">Building your quiz…</p>
      </div>
    );
  }

  // Quiz in progress
  if (phase === 'quiz' && quiz) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-8">
        <QuizView
          quiz={quiz}
          onSubmit={handleSubmit}
          onHint={handleHint}
          onRetryWrong={(quizId) => api.retryWrongQuiz(quizId)}
          onRetake={handleRetake}
          onDone={handleRetake}
          onPracticeTopic={practiceTopic}
        />
      </div>
    );
  }

  // Topic selection
  return (
    <div className="max-w-3xl mx-auto px-5 py-8 space-y-6 animate-fade-in">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 bg-gradient-to-br from-brand-500 to-brand-700 text-white rounded-2xl mb-3 shadow-soft">
          <ClipboardList size={26} />
        </div>
        <h2 className="text-2xl font-extrabold text-ink">Take a Quiz</h2>
        <p className="text-ink-muted text-sm mt-1">
          {mode === 'exam'
            ? `Exam mode · ${duration} min timer · no hints · honest score`
            : '10 MCQ + 5 written · hints available per question'}
        </p>
      </div>

      {/* B1: segmented Practice / Exam toggle */}
      <div className="flex items-center justify-center gap-3">
        <div className="inline-flex bg-slate-100 rounded-xl p-1">
          <button onClick={() => setMode('practice')}
            className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all ${mode === 'practice' ? 'bg-white text-brand-700 shadow-soft' : 'text-ink-muted hover:text-ink'}`}>
            Practice
          </button>
          <button onClick={() => setMode('exam')}
            className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all ${mode === 'exam' ? 'bg-white text-red-600 shadow-soft' : 'text-ink-muted hover:text-ink'}`}>
            Exam
          </button>
        </div>
        {mode === 'exam' && (
          <select value={duration} onChange={(e) => setDuration(Number(e.target.value))} className="input-field text-sm py-2 w-auto">
            <option value={10}>10 min</option>
            <option value={15}>15 min</option>
            <option value={30}>30 min</option>
            <option value={60}>60 min</option>
          </select>
        )}
      </div>

      {error && <p className="text-red-600 text-sm bg-red-50 border border-red-100 p-3 rounded-xl text-center">{error}</p>}

      {/* Fix my weak spots — one-tap targeted practice from your own mistakes */}
      <button
        onClick={startWeakSpots}
        className="w-full text-left rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50 to-teal-50 p-4 shadow-soft hover:shadow-md transition-shadow"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 text-[#201a0e]"
            style={{ background: 'linear-gradient(180deg,#ecd9a8,#cfa654)' }}>
            <Target size={20} />
          </div>
          <div className="min-w-0">
            <h3 className="font-bold text-ink">Fix my weak spots</h3>
            <p className="text-xs text-ink-muted mt-0.5">
              A quick practice set built from your recent mistakes & weakest topics — no setup, just start.
            </p>
          </div>
        </div>
      </button>

      {/* C2: Full-syllabus weighted mock */}
      {studiedTopics.length > 0 && (
        <div className="rounded-2xl border border-red-100 bg-gradient-to-br from-red-50 to-orange-50 p-4 shadow-soft">
          <div className="flex items-center gap-2 mb-1">
            <Timer size={18} className="text-red-500" />
            <h3 className="font-bold text-ink">Full mock test</h3>
          </div>
          <p className="text-xs text-ink-muted mb-3">Timed exam across the whole subject — more questions from your weak areas.</p>
          <div className="flex flex-wrap gap-2">
            {[...new Set(studiedTopics)].slice(0, 6).map(subj => (
              <button key={subj} onClick={() => startMock(subj)}
                className="text-sm font-medium px-3 py-1.5 rounded-lg bg-white border border-red-200 text-red-700 hover:bg-red-600 hover:text-white hover:border-red-600 transition-colors">
                {subj}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Studied topics */}
      {studiedTopics.length > 0 && (
        <div>
          <h3 className="section-title mb-3"><Sparkles size={16} className="text-brand-500" /> Your Topics</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[...new Set(studiedTopics)].map((topic) => (
              <button key={topic} onClick={() => startQuiz(topic)}
                className="card-tight card-hover text-left group">
                <p className="font-semibold text-ink capitalize">{topic}</p>
                <p className="text-xs text-brand-600 mt-0.5 flex items-center gap-1">Quiz on your progress</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* All topics */}
      <div>
        <h3 className="section-title mb-3"><BookOpen size={16} className="text-brand-500" /> Explore Topics</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          {PRESET_TOPICS.map((topic) => (
            <button key={topic} onClick={() => startQuiz(topic)}
              className="card-tight card-hover text-center py-4">
              <p className="font-semibold text-ink text-sm">{topic}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Custom topic */}
      <div className="card">
        <h3 className="section-title mb-3">Custom Topic</h3>
        <div className="flex gap-3">
          <input className="input-field flex-1" placeholder="e.g. Machine Learning, Organic Chemistry…"
            value={customTopic} onChange={(e) => setCustomTopic(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && customTopic.trim() && startQuiz(customTopic.trim())} />
          <button onClick={() => customTopic.trim() && startQuiz(customTopic.trim())}
            className="btn-primary text-sm whitespace-nowrap" disabled={!customTopic.trim()}>
            Start
          </button>
        </div>
      </div>
    </div>
  );
}
