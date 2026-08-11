import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import { ArrowLeft, Pencil, Check, X, Settings, LogOut, Flame, Trophy, Target, CheckCircle2, BookOpen } from 'lucide-react';

export default function Profile() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [p, setP] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState('');
  const [goal, setGoal] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const load = async () => {
    try {
      const data = await api.getProfile();
      setP(data);
      setName(data.display_name || '');
      setGoal(data.goal || '');
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!name.trim()) { setErr("Name can't be empty"); return; }
    setSaving(true); setErr('');
    try {
      await api.updateProfile({ display_name: name.trim(), goal: goal.trim() });
      setP(prev => ({ ...prev, display_name: name.trim(), goal: goal.trim() }));
      setEditing(false);
    } catch (e) { setErr(e.message || 'Could not save'); }
    finally { setSaving(false); }
  };

  const handleLogout = () => { logout(); navigate('/login'); };

  if (loading) {
    return (
      <div className="max-w-lg lg:max-w-2xl mx-auto px-4 lg:px-6 py-6 space-y-4">
        <div className="skeleton h-28 w-full rounded-2xl" />
        <div className="grid grid-cols-2 gap-3"><div className="skeleton h-20" /><div className="skeleton h-20" /></div>
        <div className="skeleton h-24 w-full" />
      </div>
    );
  }
  if (!p) return <p className="text-center text-ink-muted py-16">Couldn't load your profile.</p>;

  const initial = (p.display_name || p.username || '?')[0]?.toUpperCase();

  return (
    <div className="max-w-lg lg:max-w-2xl mx-auto px-4 lg:px-6 py-6 lg:py-8 space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="btn-ghost !px-2 lg:hidden"><ArrowLeft size={20} /></button>
        <h2 className="text-xl font-extrabold text-ink">Profile</h2>
      </div>

      {/* Identity card */}
      <div className="card">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 text-white flex items-center justify-center text-2xl font-bold shadow-soft flex-shrink-0">
            {initial}
          </div>
          <div className="flex-1 min-w-0">
            {!editing ? (
              <>
                <p className="text-lg font-bold text-ink truncate capitalize">{p.display_name}</p>
                <p className="text-sm text-ink-muted">@{p.username}</p>
                <span className="inline-flex items-center gap-1 mt-1.5 pill bg-brand-50 text-brand-700 capitalize">{p.role}</span>
              </>
            ) : (
              <input
                className="input-field text-sm"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Display name"
                maxLength={40}
                autoFocus
              />
            )}
          </div>
          {!editing ? (
            <button onClick={() => setEditing(true)} className="btn-secondary !py-2 !px-3 text-sm"><Pencil size={15} /> Edit</button>
          ) : (
            <div className="flex gap-2">
              <button onClick={save} disabled={saving} className="btn-primary !py-2 !px-3 text-sm"><Check size={15} /> {saving ? '…' : 'Save'}</button>
              <button onClick={() => { setEditing(false); setName(p.display_name || ''); setGoal(p.goal || ''); setErr(''); }} className="btn-secondary !py-2 !px-3"><X size={15} /></button>
            </div>
          )}
        </div>
        {err && <p className="text-sm text-red-600 mt-2">{err}</p>}

        {/* Goal */}
        <div className="mt-4 pt-4 border-t border-slate-100">
          <p className="text-xs font-semibold text-ink-faint uppercase tracking-wide mb-1.5">Learning goal</p>
          {!editing ? (
            <p className="text-sm text-ink-soft">{p.goal || <span className="text-ink-faint italic">No goal set yet — tap Edit to add one.</span>}</p>
          ) : (
            <textarea
              className="input-field text-sm resize-none"
              rows={2}
              value={goal}
              onChange={e => setGoal(e.target.value)}
              placeholder="e.g. Ace my calculus final"
              maxLength={200}
            />
          )}
        </div>

        {/* Interests */}
        {p.interests?.length > 0 && (
          <div className="mt-3">
            <p className="text-xs font-semibold text-ink-faint uppercase tracking-wide mb-1.5">Interests</p>
            <div className="flex flex-wrap gap-1.5">
              {p.interests.map((it, i) => (
                <span key={i} className="pill bg-slate-100 text-slate-600">{it}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard icon={<Flame size={18} className="text-accent-500" />} value={p.streak} label="Day streak" />
        <StatCard icon={<Trophy size={18} className="text-brand-500" />} value={`Lv ${p.level}`} label={`${p.xp} XP`} />
        <StatCard icon={<Target size={18} className="text-green-600" />} value={`${p.accuracy}%`} label="Accuracy" />
        <StatCard icon={<BookOpen size={18} className="text-indigo-500" />} value={p.topics_count} label="Topics" />
      </div>

      {/* Account rows */}
      <div className="card-tight divide-y divide-slate-100">
        <Row label="Questions answered" value={p.total_questions} />
        {p.age_band && <Row label="Age group" value={p.age_band} />}
        <Row label="Onboarding" value={p.onboarded ? 'Complete' : 'Not finished'}
             valueClass={p.onboarded ? 'text-green-600' : 'text-amber-600'} />
      </div>

      {/* Actions */}
      <div className="space-y-2">
        <button onClick={() => navigate('/settings')} className="w-full card-tight card-hover flex items-center gap-3 text-left">
          <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center flex-shrink-0"><Settings size={18} className="text-ink-soft" /></div>
          <div className="flex-1"><p className="font-semibold text-ink text-sm">Settings</p><p className="text-xs text-ink-muted">Language, reading level, reminders</p></div>
        </button>
        <button onClick={handleLogout} className="w-full card-tight flex items-center gap-3 text-left hover:bg-red-50 transition-colors">
          <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center flex-shrink-0"><LogOut size={18} className="text-red-500" /></div>
          <div className="flex-1"><p className="font-semibold text-red-600 text-sm">Log out</p></div>
        </button>
      </div>
    </div>
  );
}

function StatCard({ icon, value, label }) {
  return (
    <div className="card-tight text-center">
      <div className="flex justify-center mb-1">{icon}</div>
      <p className="text-lg font-extrabold text-ink leading-none">{value}</p>
      <p className="text-[11px] text-ink-faint font-medium mt-1">{label}</p>
    </div>
  );
}

function Row({ label, value, valueClass = 'text-ink' }) {
  return (
    <div className="flex items-center justify-between py-2.5 px-1">
      <span className="text-sm text-ink-muted">{label}</span>
      <span className={`text-sm font-semibold capitalize ${valueClass}`}>{value}</span>
    </div>
  );
}
