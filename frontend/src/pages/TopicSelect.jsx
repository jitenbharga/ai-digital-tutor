import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { BookOpen, Calculator, Beaker, Globe, Code, Atom, Brain, BarChart3, Shapes, CheckCircle2 } from 'lucide-react';

const ICON_MAP = {
  calculator: Calculator,
  brain: Brain,
  atom: Atom,
  beaker: Beaker,
  globe: Globe,
  code: Code,
  bar_chart: BarChart3,
  shapes: Shapes,
};

const FALLBACK_SUBJECTS = [
  { id: 'algebra', title: 'Algebra', icon: 'calculator', color: '#3B82F6', started: false },
  { id: 'calculus', title: 'Calculus', icon: 'brain', color: '#8B5CF6', started: false },
  { id: 'physics', title: 'Physics', icon: 'atom', color: '#10B981', started: false },
  { id: 'chemistry', title: 'Chemistry', icon: 'beaker', color: '#F59E0B', started: false },
  { id: 'biology', title: 'Biology', icon: 'globe', color: '#059669', started: false },
  { id: 'computer_science', title: 'Computer Science', icon: 'code', color: '#6366F1', started: false },
  { id: 'statistics', title: 'Statistics', icon: 'bar_chart', color: '#EC4899', started: false },
  { id: 'geometry', title: 'Geometry', icon: 'shapes', color: '#14B8A6', started: false },
];

export default function TopicSelect() {
  const [subjects, setSubjects] = useState(FALLBACK_SUBJECTS);
  const [custom, setCustom] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    api.getSubjects()
      .then(data => { if (data?.subjects?.length) setSubjects(data.subjects); })
      .catch(() => {});
  }, []);

  const handleSubject = (sub) => {
    navigate(`/curriculum/${encodeURIComponent(sub.id)}`);
  };

  const handleCustomStart = (topic) => {
    navigate('/tutor', { state: { topic } });
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-gray-900">What do you want to learn?</h2>
        <p className="text-gray-500 text-sm mt-1">Pick a subject to see its curriculum map</p>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-6">
        {subjects.map((sub) => {
          const Icon = ICON_MAP[sub.icon] || BookOpen;
          return (
            <button
              key={sub.id}
              onClick={() => handleSubject(sub)}
              className="border rounded-2xl p-4 flex items-center gap-3 hover:shadow-md transition-all active:scale-[0.98] text-left bg-white border-gray-100 relative"
            >
              <div
                className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: `${sub.color}15` }}
              >
                <Icon size={22} style={{ color: sub.color }} />
              </div>
              <span className="text-sm font-semibold text-gray-800">{sub.title}</span>
              {sub.started && (
                <CheckCircle2 size={16} className="absolute top-2 right-2 text-green-500" />
              )}
            </button>
          );
        })}
      </div>

      <form onSubmit={e => { e.preventDefault(); if (custom.trim()) handleCustomStart(custom.trim()); }}
        className="flex gap-2">
        <input
          className="flex-1 px-4 py-3 rounded-2xl border border-gray-200 bg-white text-base focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-400 transition-shadow"
          placeholder="Or type any topic for free-form tutoring..."
          value={custom}
          onChange={e => setCustom(e.target.value)}
        />
        <button type="submit" className="btn-primary rounded-2xl px-5" disabled={!custom.trim()}>Go</button>
      </form>
    </div>
  );
}
