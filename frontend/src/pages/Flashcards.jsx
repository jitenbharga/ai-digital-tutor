import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { ArrowLeft, Layers, RotateCw, PartyPopper, CheckCircle2, WifiOff } from 'lucide-react';
import Markdown from '../components/Markdown';

// ── Offline support (PWA): cache the due deck + queue grades while offline ──
const CACHE_KEY = 'fc_cache';
const QUEUE_KEY = 'fc_queue';
const readJSON = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
const writeJSON = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* full/blocked */ } };

async function flushGradeQueue() {
  if (!navigator.onLine) return readJSON(QUEUE_KEY, []).length;
  const q = readJSON(QUEUE_KEY, []);
  if (!q.length) return 0;
  const remaining = [];
  for (const g of q) {
    try { await api.gradeFlashcard(g.card_id, g.rating); }
    catch { remaining.push(g); }
  }
  writeJSON(QUEUE_KEY, remaining);
  return remaining.length;
}

/**
 * B3: Flashcards — auto-built from your mistakes + notebook highlights,
 * scheduled with FSRS. Flip → grade (Again/Hard/Good/Easy) → next.
 * Works offline: the due deck is cached and grades are queued + synced later.
 */
export default function Flashcards() {
  const navigate = useNavigate();
  const [cards, setCards] = useState([]);
  const [stats, setStats] = useState({ due_count: 0, total: 0 });
  const [idx, setIdx] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [reviewed, setReviewed] = useState(0);
  const [offline, setOffline] = useState(!navigator.onLine);
  const [queued, setQueued] = useState(readJSON(QUEUE_KEY, []).length);

  useEffect(() => {
    (async () => {
      // Sync any grades saved while offline, first.
      setQueued(await flushGradeQueue());
      try {
        if (navigator.onLine) await api.syncFlashcards(); // new mistakes/notes, retire resolved
        const d = await api.dueFlashcards();
        setCards(d.cards || []);
        setStats({ due_count: d.due_count, total: d.total });
        writeJSON(CACHE_KEY, { cards: d.cards || [], stats: { due_count: d.due_count, total: d.total } });
        setOffline(false);
      } catch {
        // Offline / fetch failed → fall back to the cached deck.
        const cached = readJSON(CACHE_KEY, null);
        if (cached) {
          setCards(cached.cards || []);
          setStats(cached.stats || { due_count: 0, total: 0 });
          setOffline(true);
        }
      }
      setLoading(false);
    })();
  }, []);

  // Flush queued grades when the connection comes back.
  useEffect(() => {
    const onOnline = async () => { setOffline(false); setQueued(await flushGradeQueue()); };
    const onOffline = () => setOffline(true);
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
    };
  }, []);

  const grade = async (rating) => {
    const card = cards[idx];
    if (!card) return;
    // Try to send; if offline / fails, queue it for later sync.
    api.gradeFlashcard(card.card_id, rating).catch(() => {
      const q = readJSON(QUEUE_KEY, []);
      q.push({ card_id: card.card_id, rating });
      writeJSON(QUEUE_KEY, q);
      setQueued(q.length);
    });
    setReviewed(r => r + 1);
    setFlipped(false);
    setIdx(i => i + 1);
  };

  if (loading) {
    return (
      <div className="max-w-lg mx-auto px-4 py-6 space-y-5 animate-fade-in">
        <div className="skeleton h-8 w-40" />
        <div className="skeleton h-64 w-full rounded-3xl" />
        <div className="grid grid-cols-4 gap-2">
          <div className="skeleton h-12" /><div className="skeleton h-12" /><div className="skeleton h-12" /><div className="skeleton h-12" />
        </div>
      </div>
    );
  }

  const card = cards[idx];

  // Empty deck or session finished
  if (!card) {
    return (
      <div className="max-w-lg mx-auto px-4 py-16 text-center space-y-4 animate-fade-in">
        {reviewed > 0 ? (
          <>
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-3xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-soft mx-auto"><PartyPopper size={30} /></div>
            <h2 className="text-2xl font-extrabold text-ink">{reviewed} cards reviewed!</h2>
            <p className="text-ink-muted text-sm">FSRS will bring them back right before you'd forget.</p>
          </>
        ) : stats.total === 0 ? (
          <>
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-3xl bg-slate-100 text-slate-400 mx-auto"><Layers size={30} /></div>
            <h2 className="text-xl font-extrabold text-ink">No cards yet</h2>
            <p className="text-ink-muted text-sm max-w-xs mx-auto">Cards build themselves from your quiz mistakes and notebook highlights. Take a quiz or save a highlight first.</p>
          </>
        ) : (
          <>
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-3xl bg-green-50 text-green-500 mx-auto"><CheckCircle2 size={30} /></div>
            <h2 className="text-xl font-extrabold text-ink">All caught up</h2>
            <p className="text-ink-muted text-sm">{stats.total} cards in your deck — none due right now.</p>
          </>
        )}
        <button onClick={() => navigate('/')} className="btn-primary mx-auto">Back home</button>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-5 animate-fade-in">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/')} className="btn-ghost !px-2"><ArrowLeft size={20} /></button>
        <div>
          <h2 className="text-xl font-extrabold text-ink">Flashcards</h2>
          <p className="text-xs text-ink-muted">{stats.due_count} due · {stats.total} in deck</p>
        </div>
        <span className="ml-auto text-sm font-bold text-brand-600">{idx + 1}/{cards.length}</span>
      </div>

      {(offline || queued > 0) && (
        <div className="flex items-center gap-2 text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded-xl px-3 py-2">
          <WifiOff size={14} className="flex-shrink-0" />
          {offline ? 'Offline — reviewing your cached deck.' : 'Back online.'}
          {queued > 0 && <span className="font-medium">{queued} grade{queued > 1 ? 's' : ''} will sync.</span>}
        </div>
      )}

      {/* Progress bar */}
      <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
        <div className="h-full bg-brand-500 rounded-full transition-all duration-300" style={{ width: `${((idx) / cards.length) * 100}%` }} />
      </div>

      {/* Card */}
      <button onClick={() => setFlipped(!flipped)}
        className="w-full min-h-[260px] bg-white border border-slate-200 rounded-3xl p-6 text-left shadow-card hover:shadow-lg transition-all flex flex-col active:scale-[0.99]">
        <span className={`pill self-start mb-3 ${card.source === 'mistake' ? 'bg-red-50 text-red-600' : 'bg-teal-50 text-teal-600'}`}>
          {card.source === 'mistake' ? 'From a mistake' : 'From your notebook'}{card.topic ? ` · ${card.topic}` : ''}
        </span>
        <div className="flex-1 prose prose-sm max-w-none flex items-center">
          <div className="w-full"><Markdown>{flipped ? card.back : card.front}</Markdown></div>
        </div>
        <span className="text-xs text-ink-faint mt-4 flex items-center gap-1 self-center">
          <RotateCw size={12} /> {flipped ? 'Tap to see the question' : 'Tap to reveal the answer'}
        </span>
      </button>

      {/* Grade buttons — only after flip */}
      {flipped ? (
        <div className="grid grid-cols-4 gap-2 animate-fade-in">
          <button onClick={() => grade('again')} className="py-3 rounded-xl bg-red-100 text-red-700 text-sm font-bold hover:bg-red-200 active:scale-95 transition-all">Again</button>
          <button onClick={() => grade('hard')} className="py-3 rounded-xl bg-amber-100 text-amber-700 text-sm font-bold hover:bg-amber-200 active:scale-95 transition-all">Hard</button>
          <button onClick={() => grade('good')} className="py-3 rounded-xl bg-green-100 text-green-700 text-sm font-bold hover:bg-green-200 active:scale-95 transition-all">Good</button>
          <button onClick={() => grade('easy')} className="py-3 rounded-xl bg-blue-100 text-blue-700 text-sm font-bold hover:bg-blue-200 active:scale-95 transition-all">Easy</button>
        </div>
      ) : (
        <p className="text-center text-xs text-gray-400">Think of the answer, then tap the card.</p>
      )}
    </div>
  );
}
