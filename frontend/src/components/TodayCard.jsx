import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';

const TYPE_STYLES = {
  learn:    { color: 'text-brand-400', bg: 'bg-brand-500/10', label: 'Learn' },
  review:   { color: 'text-amber-400', bg: 'bg-amber-500/10', label: 'Review' },
  practice: { color: 'text-purple-400', bg: 'bg-purple-500/10', label: 'Practice' },
};

export default function TodayCard() {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.getToday()
      .then(setPlan)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return null;
  if (!plan || plan.tasks.length === 0) return null;

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 mb-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-white">Today's Plan</h2>
        {plan.has_path && (
          <button
            onClick={() => navigate('/path')}
            className="text-sm text-brand-400 hover:text-brand-300 transition-colors"
          >
            View path →
          </button>
        )}
      </div>

      <div className="space-y-2">
        {plan.tasks.map((task, i) => {
          const style = TYPE_STYLES[task.type] || TYPE_STYLES.learn;
          return (
            <div
              key={i}
              className="flex items-center justify-between p-3 rounded-lg bg-gray-800 border border-gray-700"
            >
              <div className="flex items-center gap-3">
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${style.bg} ${style.color}`}>
                  {style.label}
                </span>
                <div>
                  <p className="text-white font-medium capitalize">{task.topic}</p>
                  <p className="text-xs text-gray-400">{task.reason}</p>
                </div>
              </div>
              <button
                onClick={() => navigate(`/tutor?topic=${encodeURIComponent(task.topic)}`)}
                className="px-3 py-1.5 text-sm bg-brand-600 hover:bg-brand-500 text-white rounded-md font-medium transition-colors"
              >
                Start
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
