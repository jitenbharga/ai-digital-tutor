import { useEffect } from 'react';
import { api } from '../lib/api';

/**
 * Smart study nudges via the browser Notification API.
 * Fires gentle, throttled reminders (once/day per type) based on real state:
 *   - an exam is within 7 days (+ today's task count)
 *   - reviews are due
 * Works while the app is open (or the installed PWA is reopened). Opt-in only.
 */

const KEY = 'smart_nudges_on';

export function nudgesEnabled() {
  try { return localStorage.getItem(KEY) === '1'; } catch { return false; }
}

export async function enableNudges() {
  if (!('Notification' in window)) return false;
  let perm = Notification.permission;
  if (perm === 'default') perm = await Notification.requestPermission();
  if (perm === 'granted') { localStorage.setItem(KEY, '1'); return true; }
  return false;
}

export function disableNudges() {
  try { localStorage.setItem(KEY, '0'); } catch { /* no-op */ }
}

const today = () => new Date().toISOString().slice(0, 10);
const firedToday = (type) => {
  try { return localStorage.getItem(`nudge_${type}`) === today(); } catch { return false; }
};
const markFired = (type) => {
  try { localStorage.setItem(`nudge_${type}`, today()); } catch { /* no-op */ }
};
const notify = (title, body, tag) => {
  try { new Notification(title, { body, tag, icon: '/icons/icon-192.png' }); } catch { /* blocked */ }
};

export function useSmartNudges() {
  useEffect(() => {
    if (!nudgesEnabled()) return;
    if (!('Notification' in window) || Notification.permission !== 'granted') return;

    let cancelled = false;
    const run = async () => {
      // 1) Exam proximity
      if (!firedToday('exam')) {
        try {
          const ne = await api.getNextExam();
          if (!cancelled && ne?.has_exam && ne.days_to_exam <= 7) {
            const d = ne.days_to_exam;
            const when = d === 0 ? 'is today' : d === 1 ? 'is tomorrow' : `in ${d} days`;
            const tasks = ne.today_count > 0 ? ` · ${ne.today_count} task${ne.today_count > 1 ? 's' : ''} today` : '';
            notify(`📅 ${ne.subject} exam ${when}`, `Open your plan${tasks}`, 'exam');
            markFired('exam');
          }
        } catch { /* ignore */ }
      }
      // 2) Reviews due
      if (!cancelled && !firedToday('review')) {
        try {
          const rd = await api.getReviewDueCount();
          if (!cancelled && rd?.count > 0) {
            notify('🔁 Time to review', `${rd.count} topic${rd.count > 1 ? 's' : ''} due — a few minutes keeps them fresh.`, 'review');
            markFired('review');
          }
        } catch { /* ignore */ }
      }
    };

    // Small delay so it doesn't fire during the initial page-load rush.
    const t = setTimeout(run, 4000);
    return () => { cancelled = true; clearTimeout(t); };
  }, []);
}
