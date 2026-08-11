import { useState, useEffect, useCallback } from 'react';
import { MessageSquare, Plus, Trash2, ChevronLeft, ChevronRight, History } from 'lucide-react';
import { api } from '../lib/api';

// Relative "time ago" for chat rows.
function timeAgo(ts) {
  if (!ts) return '';
  const secs = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (secs < 60) return 'just now';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(ts * 1000).toLocaleDateString();
}

/**
 * Left sidebar listing this topic's chats, most-recent-first. Click a chat to
 * resume it exactly where it ended; "New chat" starts a fresh session without
 * deleting the old one.
 *
 * Props:
 *   topic          - only chats for this topic are shown
 *   currentChatId  - id of the chat currently open (highlighted)
 *   refreshKey     - bump this number to force a reload (after save/new/delete)
 *   onSelectChat   - (chat) => void   resume an existing chat
 *   onNewChat      - () => void        start a new chat in the current topic
 */
export default function ChatHistorySidebar({ topic, currentChatId, refreshKey, onSelectChat, onNewChat }) {
  // Start collapsed on phones/tablets (<lg) so it doesn't squeeze the chat; open on desktop.
  const [open, setOpen] = useState(() => (typeof window !== 'undefined' ? window.innerWidth >= 1024 : true));
  const closeOnMobile = () => { if (typeof window !== 'undefined' && window.innerWidth < 1024) setOpen(false); };
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      // Only this topic's chats — not every topic's.
      const res = await api.listChats(topic);
      setChats(res.chats || []);
    } catch {
      setChats([]);
    } finally {
      setLoading(false);
    }
  }, [topic]);

  useEffect(() => { load(); }, [load, refreshKey]);

  const handleDelete = async (e, chatId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this chat permanently?')) return;
    try {
      await api.deleteChat(chatId);
      setChats((prev) => prev.filter((c) => c.chat_id !== chatId));
    } catch { /* ignore */ }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex-shrink-0 w-9 border-r border-gray-200 bg-white hover:bg-gray-50 flex flex-col items-center pt-3 gap-2 text-gray-400"
        title="Show chat history"
      >
        <ChevronRight size={16} />
        <History size={16} />
      </button>
    );
  }

  return (
    <>
      {/* Mobile backdrop — tap to dismiss the drawer */}
      <div className="lg:hidden fixed inset-0 bg-black/30 z-40" onClick={() => setOpen(false)} aria-hidden="true" />
      <div className="flex-shrink-0 w-64 border-r border-gray-200 bg-white flex flex-col h-full
                      max-lg:fixed max-lg:inset-0 max-lg:z-50 max-lg:w-full max-lg:shadow-2xl drawer-opaque">
      {/* Header — shows the current topic */}
      <div className="px-3 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-gray-800 min-w-0">
          <History size={16} className="text-brand-600 flex-shrink-0" />
          <span className="truncate" title={`${topic} chats`}>{topic} chats</span>
        </div>
        <button
          onClick={() => setOpen(false)}
          className="text-gray-400 hover:text-gray-600 flex-shrink-0"
          title="Hide"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      {/* New chat */}
      <div className="p-2 border-b border-gray-100">
        <button
          onClick={() => { onNewChat(); closeOnMobile(); }}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-brand-50 text-brand-700 hover:bg-brand-100 text-sm font-medium transition-colors"
        >
          <Plus size={16} /> New chat
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {loading && <p className="text-xs text-gray-400 px-2 py-3">Loading…</p>}
        {!loading && chats.length === 0 && (
          <p className="text-xs text-gray-400 px-2 py-3">
            No {topic} chats yet. Start chatting and they'll appear here.
          </p>
        )}
        {chats.map((c) => {
          const active = c.chat_id === currentChatId;
          return (
            <div
              key={c.chat_id}
              onClick={() => { onSelectChat(c); closeOnMobile(); }}
              className={`group flex items-start gap-2 px-2 py-2 rounded-lg cursor-pointer mb-0.5 transition-colors ${
                active ? 'bg-brand-100 dark:bg-brand-500/20' : 'hover:bg-gray-100 dark:hover:bg-white/5'
              }`}
            >
              <MessageSquare size={15} className={`mt-0.5 flex-shrink-0 ${active ? 'text-brand-600 dark:text-brand-300' : 'text-gray-400'}`} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-800 truncate">{c.title || c.topic}</p>
                {c.preview && <p className="text-xs text-gray-400 truncate">{c.preview}</p>}
                <p className="text-[10px] text-gray-400 mt-0.5">
                  {timeAgo(c.updated_at)} · {c.message_count || 0} msgs
                </p>
              </div>
              <button
                onClick={(e) => handleDelete(e, c.chat_id)}
                className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-500 transition-opacity flex-shrink-0"
                title="Delete chat"
              >
                <Trash2 size={14} />
              </button>
            </div>
          );
        })}
      </div>
      </div>
    </>
  );
}
