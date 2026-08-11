import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';

const STEPS = ['profile', 'interests', 'goal', 'placement'];

const INTEREST_OPTIONS = [
  'Math', 'Science', 'Programming', 'History', 'Languages',
  'Art', 'Music', 'Sports', 'Reading', 'Puzzles',
];

export default function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Profile state
  const [displayName, setDisplayName] = useState('');
  const [ageBand, setAgeBand] = useState('');

  // Interests
  const [interests, setInterests] = useState([]);

  // Goal
  const [goal, setGoal] = useState('');

  // Placement quiz state
  const [sessionId, setSessionId] = useState(null);
  const [question, setQuestion] = useState(null);
  const [options, setOptions] = useState(null);
  const [topic, setTopic] = useState('');
  const [qNum, setQNum] = useState(0);
  const [totalQ, setTotalQ] = useState(5);
  const [feedback, setFeedback] = useState(null);
  const [results, setResults] = useState(null);

  const toggleInterest = (item) => {
    setInterests(prev =>
      prev.includes(item) ? prev.filter(i => i !== item) : [...prev, item]
    );
  };

  const startPlacement = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.onboardingStart({
        display_name: displayName,
        age_band: ageBand,
        interests,
        goal,
      });
      setSessionId(data.session_id);
      setQuestion(data.question);
      setOptions(data.options);
      setTopic(data.topic);
      setQNum(data.question_number);
      setTotalQ(data.total_questions);
      setStep(3);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async (answer) => {
    setLoading(true);
    setFeedback(null);
    try {
      const data = await api.onboardingAnswer(sessionId, answer);
      setFeedback(data.correct ? 'Correct!' : 'Not quite.');

      if (data.done) {
        // Complete onboarding
        const result = await api.onboardingComplete(sessionId);
        setResults(result);
      } else {
        // Move to next question after brief delay
        setTimeout(() => {
          setFeedback(null);
          setQuestion(data.next_question);
          setOptions(data.next_options);
          setTopic(data.next_topic);
          setQNum(data.question_number);
        }, 800);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const finish = () => navigate('/');

  // Results screen
  if (results) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full text-center">
          <h1 className="text-2xl font-bold mb-2">Welcome, {results.display_name}!</h1>
          <p className="text-gray-600 mb-6">{results.message}</p>
          <div className="text-left mb-6">
            <h3 className="font-semibold mb-2">Your placement results:</h3>
            {Object.entries(results.mastery_seeds).map(([t, m]) => (
              <div key={t} className="flex justify-between py-1">
                <span>{t}</span>
                <span className="font-mono">{Math.round(m * 100)}%</span>
              </div>
            ))}
          </div>
          <button
            onClick={finish}
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700"
          >
            Start Learning
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full">
        {/* Progress bar */}
        <div className="flex gap-2 mb-8">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 flex-1 rounded-full ${i <= step ? 'bg-blue-600' : 'bg-gray-200'}`}
            />
          ))}
        </div>

        {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

        {/* Step 0: Profile */}
        {step === 0 && (
          <div>
            <h2 className="text-xl font-bold mb-1">What should we call you?</h2>
            <p className="text-gray-500 text-sm mb-6">Pick a display name and your age group.</p>
            <input
              type="text"
              placeholder="Display name"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              className="w-full border rounded-lg px-4 py-3 mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            <div className="flex gap-2 mb-6">
              {['under-13', '13-17', '18+'].map(ab => (
                <button
                  key={ab}
                  onClick={() => setAgeBand(ab)}
                  className={`flex-1 py-2 rounded-lg border text-sm font-medium ${
                    ageBand === ab ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'
                  }`}
                >
                  {ab}
                </button>
              ))}
            </div>
            {ageBand === 'under-13' && (
              <p className="text-red-600 text-sm mb-3 bg-red-50 p-3 rounded-lg">
                This product is currently available for users aged 13 and above. Please come back when you're older, or ask a parent to help set up a compliant account.
              </p>
            )}
            <button
              disabled={!displayName || !ageBand || ageBand === 'under-13'}
              onClick={() => setStep(1)}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium disabled:opacity-40 hover:bg-blue-700"
            >
              Next
            </button>
          </div>
        )}

        {/* Step 1: Interests */}
        {step === 1 && (
          <div>
            <h2 className="text-xl font-bold mb-1">What interests you?</h2>
            <p className="text-gray-500 text-sm mb-6">Pick as many as you like.</p>
            <div className="flex flex-wrap gap-2 mb-6">
              {INTEREST_OPTIONS.map(item => (
                <button
                  key={item}
                  onClick={() => toggleInterest(item)}
                  className={`px-4 py-2 rounded-full text-sm font-medium border ${
                    interests.includes(item)
                      ? 'bg-blue-100 text-blue-700 border-blue-300'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
                  }`}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <button onClick={() => setStep(0)} className="flex-1 border border-gray-300 py-3 rounded-lg">Back</button>
              <button onClick={() => setStep(2)} className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700">Next</button>
            </div>
          </div>
        )}

        {/* Step 2: Goal */}
        {step === 2 && (
          <div>
            <h2 className="text-xl font-bold mb-1">What's your learning goal?</h2>
            <p className="text-gray-500 text-sm mb-6">One sentence is enough.</p>
            <textarea
              placeholder="e.g. Prepare for my math exam next month"
              value={goal}
              onChange={e => setGoal(e.target.value)}
              rows={3}
              className="w-full border rounded-lg px-4 py-3 mb-6 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              autoFocus
            />
            <div className="flex gap-2">
              <button onClick={() => setStep(1)} className="flex-1 border border-gray-300 py-3 rounded-lg">Back</button>
              <button
                onClick={startPlacement}
                disabled={loading}
                className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-medium disabled:opacity-40 hover:bg-blue-700"
              >
                {loading ? 'Starting...' : 'Start Placement Quiz'}
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Placement Quiz */}
        {step === 3 && question && (
          <div>
            <div className="flex justify-between items-center mb-4">
              <span className="text-sm text-gray-500">Question {qNum} / {totalQ}</span>
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">{topic}</span>
            </div>
            <h2 className="text-lg font-semibold mb-6">{question}</h2>

            {feedback && (
              <p className={`text-center font-semibold mb-4 ${feedback === 'Correct!' ? 'text-green-600' : 'text-red-500'}`}>
                {feedback}
              </p>
            )}

            {options && !feedback && (
              <div className="space-y-3">
                {Object.entries(options).map(([key, val]) => (
                  <button
                    key={key}
                    onClick={() => submitAnswer(key)}
                    disabled={loading}
                    className="w-full text-left border rounded-lg px-4 py-3 hover:bg-blue-50 hover:border-blue-400 disabled:opacity-40"
                  >
                    <span className="font-mono text-blue-600 mr-2">{key}.</span>
                    {val}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
