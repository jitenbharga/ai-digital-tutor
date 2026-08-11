import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import { RefreshCw, Check, X, ArrowRight, Trophy, ChevronRight } from 'lucide-react';
import CertificateModal from '../components/CertificateModal';

export default function Review() {
  const { user } = useAuth();
  const studentId = user?.username || 'anon';

  const [loading, setLoading] = useState(true);
  const [dueTops, setDueTops] = useState([]);
  const [question, setQuestion] = useState(null);
  const [currentTopic, setCurrentTopic] = useState(null);
  const [answer, setAnswer] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [done, setDone] = useState(0);
  const [total, setTotal] = useState(0);
  const [sessionDone, setSessionDone] = useState(false);
  const [newCert, setNewCert] = useState(null);

  // Load review data
  const loadReview = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.review(studentId);
      setDueTops(data.due_topics || []);
      setQuestion(data.review_question);
      if (data.due_topics?.length > 0) {
        setCurrentTopic(data.due_topics[0].topic);
        setTotal(prev => prev === 0 ? data.due_topics.length : prev);
      } else {
        setSessionDone(true);
      }
    } catch {
      setDueTops([]);
      setSessionDone(true);
    } finally {
      setLoading(false);
    }
  }, [studentId]);

  useEffect(() => { loadReview(); }, [loadReview]);

  // Submit answer
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!answer.trim() || submitting) return;
    setSubmitting(true);
    try {
      const fb = await api.submitAnswer(studentId, answer.trim());
      setFeedback(fb);
      if (fb.new_certificate) setNewCert(fb.new_certificate);
    } catch (err) {
      setFeedback({ correct: false, feedback: `Error: ${err.message}` });
    } finally {
      setSubmitting(false);
    }
  };

  // Next question
  const handleNext = () => {
    setFeedback(null);
    setAnswer('');
    setDone(prev => prev + 1);
    loadReview();
  };

  if (loading && done === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-amber-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  // Session complete
  if (sessionDone || (dueTops.length === 0 && !loading)) {
    return (
      <div className="max-w-lg mx-auto px-4 py-12 text-center">
        <div className="w-20 h-20 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-6">
          <Trophy size={40} className="text-green-500" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          {done > 0 ? 'Review complete!' : 'Nothing to review'}
        </h2>
        <p className="text-gray-500 mb-6">
          {done > 0
            ? `You reviewed ${done} topic${done > 1 ? 's' : ''}. Nice work!`
            : 'All your topics are fresh. Come back later!'}
        </p>
        <button
          onClick={() => { setDone(0); setTotal(0); setSessionDone(false); loadReview(); }}
          className="btn-secondary inline-flex items-center gap-2"
        >
          <RefreshCw size={16} /> Check again
        </button>
      </div>
    );
  }

  const progress = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-5">
      {/* Progress header */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <RefreshCw size={20} className="text-amber-500" />
            Daily Review
          </h2>
          <span className="text-sm text-gray-400 font-medium">{done} / {total}</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-amber-500 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Topic badge */}
      {currentTopic && (
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-amber-50 text-amber-600">
            Review
          </span>
          <span className="text-sm font-medium text-gray-700 capitalize">{currentTopic}</span>
          {dueTops[0] && (
            <span className="text-xs text-gray-400 ml-auto">
              {Math.round(dueTops[0].retention_estimate * 100)}% retained
            </span>
          )}
        </div>
      )}

      {/* Question card */}
      <div className="bg-white border border-gray-200 rounded-2xl p-5">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin h-6 w-6 border-3 border-amber-500 border-t-transparent rounded-full" />
          </div>
        ) : question ? (
          <div className="space-y-3">
            {question.refresher && (
              <p className="text-sm text-amber-700 bg-amber-50 rounded-lg px-3 py-2">
                {question.refresher}
              </p>
            )}
            <p className="text-gray-900 text-base leading-relaxed whitespace-pre-wrap">
              {question.question || question}
            </p>
            {question.tests_concept && (
              <p className="text-xs text-gray-400 mt-2">Testing: {question.tests_concept}</p>
            )}
          </div>
        ) : (
          <p className="text-gray-400 text-center py-4">No question available</p>
        )}
      </div>

      {/* Feedback card */}
      {feedback && (
        <div className={`rounded-2xl p-4 border ${
          feedback.correct
            ? 'bg-green-50 border-green-200'
            : 'bg-red-50 border-red-200'
        }`}>
          <div className="flex items-start gap-3">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
              feedback.correct ? 'bg-green-100' : 'bg-red-100'
            }`}>
              {feedback.correct
                ? <Check size={18} className="text-green-600" />
                : <X size={18} className="text-red-600" />
              }
            </div>
            <div>
              <p className={`font-medium text-sm ${feedback.correct ? 'text-green-800' : 'text-red-800'}`}>
                {feedback.correct ? 'Correct!' : 'Not quite'}
              </p>
              <p className="text-sm text-gray-600 mt-1">{feedback.feedback}</p>
            </div>
          </div>
          <button
            onClick={handleNext}
            className="w-full mt-4 bg-white border border-gray-200 rounded-xl py-3 font-medium text-gray-700 hover:bg-gray-50 transition-colors flex items-center justify-center gap-2 active:scale-[0.98]"
          >
            Next <ChevronRight size={16} />
          </button>
        </div>
      )}

      {/* Answer input */}
      {!feedback && question && (
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            className="w-full px-4 py-3.5 rounded-2xl border border-gray-200 bg-white text-base focus:outline-none focus:ring-2 focus:ring-amber-500/40 focus:border-amber-400 transition-shadow"
            placeholder="Type your answer..."
            value={answer}
            onChange={e => setAnswer(e.target.value)}
            disabled={submitting}
            autoFocus
          />
          <button
            type="submit"
            disabled={!answer.trim() || submitting}
            className="w-full bg-amber-500 hover:bg-amber-600 text-white rounded-2xl py-3.5 font-semibold transition-colors disabled:opacity-50 flex items-center justify-center gap-2 active:scale-[0.98]"
          >
            {submitting ? (
              <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full" />
            ) : (
              <>Submit <ArrowRight size={18} /></>
            )}
          </button>
        </form>
      )}

      {/* Due topics list */}
      {dueTops.length > 1 && (
        <div className="text-xs text-gray-400 pt-2">
          <p className="mb-2 font-medium">Coming up:</p>
          <div className="flex flex-wrap gap-1.5">
            {dueTops.slice(1, 6).map((t, i) => (
              <span key={i} className="px-2 py-1 bg-gray-100 rounded-lg capitalize">{t.topic}</span>
            ))}
            {dueTops.length > 6 && <span className="px-2 py-1">+{dueTops.length - 6} more</span>}
          </div>
        </div>
      )}

      {/* Certificate modal */}
      {newCert && <CertificateModal certificate={newCert} onClose={() => setNewCert(null)} />}
    </div>
  );
}
