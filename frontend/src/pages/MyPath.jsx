import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';

const STATE_STYLES = {
  mastered: { bg: 'bg-green-500', border: 'border-green-400', text: 'text-white', icon: '✓' },
  current:  { bg: 'bg-brand-500', border: 'border-brand-400', text: 'text-white', icon: '▶' },
  unlocked: { bg: 'bg-gray-700', border: 'border-gray-500', text: 'text-gray-200', icon: '○' },
  locked:   { bg: 'bg-gray-800', border: 'border-gray-700', text: 'text-gray-500', icon: '🔒' },
};

export default function MyPath() {
  const [path, setPath] = useState(null);
  const [loading, setLoading] = useState(true);
  const [goalInput, setGoalInput] = useState('');
  const [setting, setSetting] = useState(false);
  const navigate = useNavigate();

  const loadPath = async () => {
    try {
      const data = await api.getPath();
      setPath(data);
    } catch (e) {
      console.error('Failed to load path:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadPath(); }, []);

  const handleSetGoal = async (e) => {
    e.preventDefault();
    if (!goalInput.trim()) return;
    setSetting(true);
    try {
      const data = await api.setPath(goalInput.trim());
      setPath(data);
      setGoalInput('');
    } catch (err) {
      alert(err.message);
    } finally {
      setSetting(false);
    }
  };

  const handleStartTopic = (topic) => {
    navigate(`/tutor?topic=${encodeURIComponent(topic)}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-brand-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto py-6 px-4 space-y-6">
      <h1 className="text-2xl font-bold text-white">My Learning Path</h1>

      {/* Goal setter */}
      <form onSubmit={handleSetGoal} className="flex gap-2">
        <input
          type="text"
          value={goalInput}
          onChange={(e) => setGoalInput(e.target.value)}
          placeholder={path?.goal ? `Current goal: ${path.goal}` : "Set your learning goal (e.g. Calculus)"}
          className="flex-1 px-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-brand-500"
          maxLength={100}
        />
        <button
          type="submit"
          disabled={setting || !goalInput.trim()}
          className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg font-medium disabled:opacity-50 transition-colors"
        >
          {setting ? 'Building...' : path?.goal ? 'Change Goal' : 'Set Goal'}
        </button>
      </form>

      {/* Progress bar */}
      {path?.goal && path.path.length > 0 && (
        <div className="space-y-1">
          <div className="flex justify-between text-sm text-gray-400">
            <span>Progress toward {path.goal}</span>
            <span>{path.progress_pct}%</span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-brand-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${path.progress_pct}%` }}
            />
          </div>
        </div>
      )}

      {/* Path roadmap */}
      {path?.path?.length > 0 ? (
        <div className="relative">
          {path.path.map((node, i) => {
            const style = STATE_STYLES[node.state] || STATE_STYLES.locked;
            const isLast = i === path.path.length - 1;

            return (
              <div key={node.topic} className="flex items-start gap-4">
                {/* Vertical line + node circle */}
                <div className="flex flex-col items-center">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold border-2 ${style.bg} ${style.border} ${style.text}`}>
                    {style.icon}
                  </div>
                  {!isLast && (
                    <div className={`w-0.5 h-12 ${node.state === 'mastered' ? 'bg-green-500' : 'bg-gray-600'}`} />
                  )}
                </div>

                {/* Topic card */}
                <div className={`flex-1 mb-4 p-3 rounded-lg border ${
                  node.state === 'current' ? 'border-brand-500 bg-brand-500/10' :
                  node.state === 'mastered' ? 'border-green-500/30 bg-green-500/5' :
                  'border-gray-700 bg-gray-800/50'
                }`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className={`font-medium capitalize ${
                        node.state === 'locked' ? 'text-gray-500' : 'text-white'
                      }`}>
                        {node.topic}
                      </h3>
                      {node.prereqs.length > 0 && (
                        <p className="text-xs text-gray-500 mt-0.5">
                          Requires: {node.prereqs.join(', ')}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      {/* Mastery indicator */}
                      <span className={`text-sm ${
                        node.mastery >= 0.8 ? 'text-green-400' :
                        node.mastery >= 0.4 ? 'text-yellow-400' :
                        'text-gray-500'
                      }`}>
                        {Math.round(node.mastery * 100)}%
                      </span>

                      {/* Action button */}
                      {(node.state === 'current' || node.state === 'unlocked') && (
                        <button
                          onClick={() => handleStartTopic(node.topic)}
                          className={`px-3 py-1 text-sm rounded-md font-medium transition-colors ${
                            node.state === 'current'
                              ? 'bg-brand-600 hover:bg-brand-500 text-white'
                              : 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                          }`}
                        >
                          {node.state === 'current' ? 'Start' : 'Study'}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center text-gray-400 py-12">
          <p className="text-lg mb-2">No learning path yet</p>
          <p className="text-sm">Set a goal above to build your personalized roadmap</p>
        </div>
      )}
    </div>
  );
}
