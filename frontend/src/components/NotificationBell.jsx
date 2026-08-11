import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { Bell, CalendarClock, Flame } from 'lucide-react';

const TYPE_ICON = {
  exam: CalendarClock,
  streak: Flame,
};

/**
 * C3: Re-engagement bell — unread count + dropdown of nudges.
 * Only meaningful for students; renders nothing if the fetch fails (e.g. guardians).
 */
export default function NotificationBell() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const load = () => {
    api.getNotifications()
      .then(r => { setItems(r.notifications || []); setUnread(r.unread || 0); })
      .catch(() => {});
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5 * 60 * 1000); // refresh every 5 min
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && unread > 0) {
      api.markNotificationsRead().then(() => setUnread(0)).catch(() => {});
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button onClick={toggle} className="relative text-gray-400 hover:text-gray-600 transition-colors" title="Notifications">
        <Bell size={18} />
        {unread > 0 && (
          <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-white border border-gray-200 rounded-2xl shadow-lg z-50 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-100 text-sm font-semibold text-gray-800">Notifications</div>
          {items.length === 0 ? (
            <p className="px-4 py-6 text-sm text-gray-400 text-center">You're all caught up 🎉</p>
          ) : (
            <div className="max-h-96 overflow-y-auto">
              {items.map((n, i) => {
                const Icon = TYPE_ICON[n.type] || Bell;
                return (
                  <button
                    key={i}
                    onClick={() => {
                      setOpen(false);
                      if (n.type === 'exam') navigate('/exam-plan');
                      else navigate('/session');
                    }}
                    className={`w-full text-left px-4 py-3 flex items-start gap-2.5 hover:bg-gray-50 transition-colors ${!n.read ? 'bg-brand-50/40' : ''}`}
                  >
                    <Icon size={15} className={n.type === 'exam' ? 'text-red-500 mt-0.5' : 'text-orange-500 mt-0.5'} />
                    <span className="text-sm text-gray-700 flex-1">{n.message}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
