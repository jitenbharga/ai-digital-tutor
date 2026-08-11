import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { Users, Flame, Copy, Check, X, UserPlus, LogIn } from 'lucide-react';

/**
 * Study buddy widget for the Home page.
 *  - No buddy → invite a friend (share code) or redeem a code.
 *  - Has buddy → shared streak + who studied today + unpair.
 * A shared streak only grows on days BOTH friends studied.
 */
export default function StudyBuddyCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState(null); // null | 'invite' | 'join'
  const [code, setCode] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    try { setData(await api.getBuddy()); }
    catch { setData({ has_buddy: false }); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const doInvite = async () => {
    setBusy(true); setError('');
    try {
      const r = await api.buddyInvite();
      setInviteCode(r.code);
      setMode('invite');
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  const doRedeem = async () => {
    if (!code.trim() || busy) return;
    setBusy(true); setError('');
    try {
      await api.buddyRedeem(code.trim());
      setMode(null); setCode('');
      await load();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  const doUnpair = async () => {
    if (!window.confirm('Unpair from your study buddy?')) return;
    setBusy(true);
    try { await api.removeBuddy(); await load(); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  const copyCode = () => {
    navigator.clipboard?.writeText(inviteCode).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 1500);
    }).catch(() => {});
  };

  if (loading) return null;

  // ── Has a buddy: shared streak view ──
  if (data?.has_buddy) {
    return (
      <div className="rounded-2xl border border-orange-200 dark:border-orange-500/25 bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-500/15 dark:to-amber-500/10 p-4 shadow-soft">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-orange-500 text-white flex items-center justify-center flex-shrink-0">
            <Flame size={22} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <p className="font-bold text-ink">
                {data.shared_streak > 0 ? `${data.shared_streak}-day shared streak` : 'Start your shared streak'}
              </p>
              <button onClick={doUnpair} disabled={busy} className="text-slate-300 hover:text-red-500 flex-shrink-0" title="Unpair"><X size={16} /></button>
            </div>
            <p className="text-xs text-ink-muted mt-0.5 capitalize">You &amp; {data.buddy}</p>
            <div className="flex items-center gap-3 mt-2 text-xs">
              <span className={`flex items-center gap-1 font-medium ${data.you_today ? 'text-green-700 dark:text-green-400' : 'text-slate-500 dark:text-slate-400'}`}>
                {data.you_today ? <Check size={13} /> : <span className="w-3 h-3 rounded-full border border-slate-400 dark:border-slate-500 inline-block" />} You today
              </span>
              <span className={`flex items-center gap-1 font-medium capitalize ${data.buddy_today ? 'text-green-700 dark:text-green-400' : 'text-slate-500 dark:text-slate-400'}`}>
                {data.buddy_today ? <Check size={13} /> : <span className="w-3 h-3 rounded-full border border-slate-400 dark:border-slate-500 inline-block" />} {data.buddy} today
              </span>
            </div>
            {!data.buddy_today && (
              <p className="text-[11px] text-amber-700 dark:text-amber-300 mt-1.5 bg-white/60 dark:bg-black/20 rounded-lg px-2 py-1">
                {data.buddy} hasn't studied yet today — keep the streak alive!
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── No buddy: invite / join ──
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-soft">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-orange-400 to-amber-500 text-white flex items-center justify-center flex-shrink-0">
          <Users size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-bold text-ink">Study with a friend</p>
          <p className="text-xs text-ink-muted mt-0.5">Pair up and build a streak only you two can keep alive.</p>
        </div>
      </div>

      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}

      {mode === 'invite' && inviteCode ? (
        <div className="mt-3 space-y-2">
          <p className="text-xs text-ink-muted">Share this code with your friend (valid 48h):</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-slate-100 rounded-lg px-3 py-2 text-sm font-mono tracking-wide text-ink break-all">{inviteCode}</code>
            <button onClick={copyCode} className="btn-secondary !px-3">{copied ? <Check size={16} className="text-green-600" /> : <Copy size={16} />}</button>
          </div>
          <button onClick={() => setMode(null)} className="btn-ghost w-full text-sm text-slate-500">Done</button>
        </div>
      ) : mode === 'join' ? (
        <div className="mt-3 space-y-2">
          <input
            className="input-field w-full text-sm"
            placeholder="Paste your friend's code"
            value={code}
            onChange={e => setCode(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && doRedeem()}
          />
          <div className="flex gap-2">
            <button onClick={doRedeem} disabled={busy || !code.trim()} className="btn-primary flex-1 text-sm">{busy ? 'Pairing…' : 'Pair up'}</button>
            <button onClick={() => { setMode(null); setError(''); }} className="btn-secondary text-sm">Cancel</button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2 mt-3">
          <button onClick={doInvite} disabled={busy} className="btn-primary flex-1 text-sm flex items-center justify-center gap-1.5">
            <UserPlus size={15} /> Invite a friend
          </button>
          <button onClick={() => { setMode('join'); setError(''); }} className="btn-secondary flex-1 text-sm flex items-center justify-center gap-1.5">
            <LogIn size={15} /> Enter a code
          </button>
        </div>
      )}
    </div>
  );
}
