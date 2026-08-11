import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { ChevronLeft, ChevronRight, CheckCircle2, Play, Circle, SkipForward, Map } from 'lucide-react';

const STATUS_ICON = {
  done: { Icon: CheckCircle2, color: 'text-green-500' },
  in_progress: { Icon: Play, color: 'text-blue-500' },
  not_started: { Icon: Circle, color: 'text-gray-300' },
  skipped: { Icon: SkipForward, color: 'text-amber-500' },
};

export default function CurriculumSidePanel({ subject, currentTopic, onSelectTopic }) {
  const navigate = useNavigate();
  // Collapsed by default on phones/tablets (<lg) so it never squeezes the chat column.
  const [open, setOpen] = useState(() => (typeof window !== 'undefined' ? window.innerWidth >= 1024 : true));
  const closeOnMobile = () => { if (typeof window !== 'undefined' && window.innerWidth < 1024) setOpen(false); };
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!subject) return;
    try {
      const res = await api.getCurriculum(subject);
      setData(res);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [subject]);

  useEffect(() => { load(); }, [load]);

  // Refresh when topic changes (user may have completed something)
  useEffect(() => {
    if (data) load();
  }, [currentTopic]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!subject) return null;

  // Collapsed state — just a thin toggle bar
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed right-0 top-1/2 -translate-y-1/2 z-30 bg-white border border-r-0 border-gray-200 rounded-l-xl px-1.5 py-4 shadow-sm hover:bg-gray-50 transition-colors"
        title="Show curriculum"
      >
        <ChevronLeft size={16} className="text-gray-500" />
        <Map size={14} className="text-gray-400 mt-1" />
      </button>
    );
  }

  const pct = data?.stats?.progress_pct || 0;

  // Build tree: level-1 topics with level-2 children
  const topics = (data?.nodes || []).filter(n => n.level === 1 && n.node_type !== 'branch');
  const chosenBranches = data?.chosen_branches || {};
  const chosenBranchNodes = (data?.nodes || []).filter(
    n => n.node_type === 'branch' && Object.values(chosenBranches).includes(n.node_id)
  );
  const allTopics = [...topics, ...chosenBranchNodes].sort((a, b) => a.order - b.order);

  const subtopicsByParent = {};
  for (const n of (data?.nodes || [])) {
    if (n.level === 2) {
      if (!subtopicsByParent[n.parent_id]) subtopicsByParent[n.parent_id] = [];
      subtopicsByParent[n.parent_id].push(n);
    }
  }

  // Find which topic matches currentTopic
  const normalizedCurrent = currentTopic?.toLowerCase();

  return (
    <>
      {/* Mobile backdrop — tap to dismiss the drawer */}
      <div className="lg:hidden fixed inset-0 bg-black/30 z-40" onClick={() => setOpen(false)} aria-hidden="true" />
      <div className="w-64 flex-shrink-0 bg-white border-l border-gray-200 h-full flex flex-col overflow-hidden
                      max-lg:fixed max-lg:inset-0 max-lg:z-50 max-lg:w-full max-lg:shadow-2xl drawer-opaque">
      {/* Header */}
      <div className="px-3 py-3 border-b border-gray-100 flex items-center gap-2">
        <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600">
          <ChevronRight size={16} />
        </button>
        <span className="text-xs font-bold text-gray-700 truncate flex-1">
          {data?.subject_title || subject}
        </span>
        <button
          onClick={() => navigate(`/curriculum/${subject}`)}
          className="text-[10px] text-brand-600 hover:text-brand-700 font-medium"
        >
          Full map
        </button>
      </div>

      {/* Progress bar */}
      <div className="px-3 py-2">
        <div className="flex justify-between text-[10px] text-gray-400 mb-1">
          <span>{data?.stats?.done || 0}/{data?.stats?.total || 0}</span>
          <span>{pct}%</span>
        </div>
        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-brand-500 rounded-full transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        {loading ? (
          <div className="flex justify-center py-8">
            <div className="animate-spin h-5 w-5 border-2 border-brand-500 border-t-transparent rounded-full" />
          </div>
        ) : (
          allTopics.map(topic => {
            const subs = subtopicsByParent[topic.node_id] || [];
            const { Icon: TIcon, color: tColor } = STATUS_ICON[topic.status] || STATUS_ICON.not_started;
            const isCurrentParent = subs.some(s => s.title.toLowerCase() === normalizedCurrent) ||
              topic.title.toLowerCase() === normalizedCurrent;

            return (
              <div key={topic.node_id}>
                {/* Topic header */}
                <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-semibold ${
                  isCurrentParent ? 'bg-brand-50 text-brand-700' : 'text-gray-700'
                }`}>
                  <TIcon size={12} className={tColor} />
                  <span className="truncate">{topic.title}</span>
                  <span className="ml-auto text-[9px] text-gray-400">
                    {Math.round(topic.mastery * 100)}%
                  </span>
                </div>

                {/* Subtopics */}
                {subs.map(sub => {
                  const { Icon: SIcon, color: sColor } = STATUS_ICON[sub.status] || STATUS_ICON.not_started;
                  const isCurrent = sub.title.toLowerCase() === normalizedCurrent;

                  return (
                    <button
                      key={sub.node_id}
                      onClick={() => { onSelectTopic?.(sub.title); closeOnMobile(); }}
                      className={`w-full flex items-center gap-1.5 pl-5 pr-2 py-1 rounded-lg text-[11px] transition-colors ${
                        isCurrent
                          ? 'bg-brand-100 text-brand-800 font-semibold'
                          : 'text-gray-600 hover:bg-gray-50'
                      }`}
                    >
                      <SIcon size={10} className={sColor} />
                      <span className="truncate text-left flex-1">{sub.title}</span>
                      {sub.mastery > 0 && (
                        <span className="text-[9px] text-gray-400">{Math.round(sub.mastery * 100)}%</span>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })
        )}
      </div>
      </div>
    </>
  );
}
