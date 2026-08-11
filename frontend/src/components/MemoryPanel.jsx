import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { Brain, Trash2, Plus } from 'lucide-react';

const CATEGORY_STYLES = {
  goal:       { bg: 'bg-blue-50',   color: 'text-blue-700',   label: 'Goal' },
  struggle:   { bg: 'bg-red-50',    color: 'text-red-700',    label: 'Struggle' },
  win:        { bg: 'bg-green-50',  color: 'text-green-700',  label: 'Win' },
  preference: { bg: 'bg-purple-50', color: 'text-purple-700', label: 'Preference' },
  general:    { bg: 'bg-gray-50',   color: 'text-gray-600',   label: 'Note' },
};

/**
 * A3: "What your tutor knows about you" — view, add, delete memory facts.
 * Transparency + control: deleting is immediate and permanent.
 */
export default function MemoryPanel() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newFact, setNewFact] = useState('');
  const [adding, setAdding] = useState(false);

  const load = () => {
    api.getMemory()
      .then(r => { setItems(r.items || []); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(load, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newFact.trim() || adding) return;
    setAdding(true);
    try {
      await api.addMemory(newFact.trim(), 'preference');
      setNewFact('');
      load();
    } catch {}
    setAdding(false);
  };

  const handleDelete = async (fact) => {
    try {
      await api.deleteMemory(fact);
      setItems(prev => prev.filter(i => i.fact !== fact));
    } catch {}
  };

  return (
    <div className="border-t pt-4">
      <h3 className="text-sm font-semibold text-gray-800 mb-1 flex items-center gap-2">
        <Brain size={16} className="text-brand-500" />
        What your tutor remembers about you
      </h3>
      <p className="text-xs text-gray-400 mb-3">
        These help personalize your lessons. Delete anything — it's removed immediately and permanently.
      </p>

      {loading ? (
        <p className="text-xs text-gray-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-xs text-gray-400 italic">Nothing yet — your tutor learns as you study.</p>
      ) : (
        <ul className="space-y-2 mb-3">
          {items.map((item, i) => {
            const st = CATEGORY_STYLES[item.category] || CATEGORY_STYLES.general;
            return (
              <li key={i} className="flex items-start gap-2 bg-white border border-gray-100 rounded-xl px-3 py-2">
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded mt-0.5 flex-shrink-0 ${st.bg} ${st.color}`}>
                  {st.label}
                </span>
                <span className="text-sm text-gray-700 flex-1">{item.fact}</span>
                <button
                  onClick={() => handleDelete(item.fact)}
                  className="text-gray-300 hover:text-red-500 transition-colors flex-shrink-0"
                  title="Forget this"
                >
                  <Trash2 size={14} />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <form onSubmit={handleAdd} className="flex gap-2">
        <input
          className="input-field flex-1 text-sm"
          placeholder="Tell your tutor something to remember…"
          value={newFact}
          onChange={e => setNewFact(e.target.value)}
          maxLength={300}
        />
        <button type="submit" className="btn-secondary px-3" disabled={!newFact.trim() || adding} title="Add">
          <Plus size={16} />
        </button>
      </form>
    </div>
  );
}
