import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import { sendEmailFrontend, emailServiceConfigured } from '../lib/emailService';
import { Users, Eye, KeyRound, ChevronLeft, Mail } from 'lucide-react';

/** B6: Weekly digest — built server-side, emailed from the browser (SMTP via smtp.js) */
function DigestCard() {
  const [email, setEmail] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [emailReady] = useState(emailServiceConfigured());
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getDigestPrefs()
      .then(p => { setEmail(p.email || ''); setEnabled(p.enabled !== false); })
      .catch(() => {});
  }, []);

  const save = async () => {
    setBusy(true); setMsg('');
    try {
      await api.setDigestPrefs({ email, enabled });
      setMsg('Saved.');
    } catch (err) { setMsg(err.message); }
    setBusy(false);
  };

  const sendNow = async () => {
    setBusy(true); setMsg('');
    try {
      const r = await api.sendDigestNow();
      const toEmail = email.trim();
      if (!toEmail) { setMsg('Enter the guardian email address first.'); return; }
      const result = await sendEmailFrontend({
        to_email: toEmail,
        recipient_name: r.recipient_name || 'Guardian',
        subject: r.subject,
        message: r.text,
      });
      setMsg(result.success
        ? `Sent to ${toEmail} — check your inbox.`
        : result.simulated
          ? 'SMTP is not configured (set VITE_SMTP_* in Vercel).'
          : 'SMTP could not send — check your SMTP settings.');
    } catch (err) { setMsg(err.message); }
    setBusy(false);
  };

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-900 mb-1 flex items-center gap-2">
        <Mail size={18} /> Weekly Digest
      </h3>
      <p className="text-sm text-gray-500 mb-3">
        Quizzes taken, scores, topics studied, mistakes fixed — per child. Sent from your browser via SMTP.
      </p>
      {!emailReady && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded-lg p-2 mb-3">
          SMTP isn't configured — set VITE_SMTP_HOST, VITE_SMTP_USER, VITE_SMTP_PASSWORD and VITE_SMTP_FROM in Vercel.
        </p>
      )}
      <div className="flex flex-wrap gap-3 items-center">
        <input
          className="input-field flex-1 min-w-0 sm:min-w-[220px]"
          type="email"
          placeholder="your@email.com"
          value={email}
          onChange={e => setEmail(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />
          Weekly
        </label>
        <button onClick={save} className="btn-primary text-sm" disabled={busy || !email}>Save</button>
        <button onClick={sendNow} className="btn-secondary text-sm" disabled={busy || !email || !emailReady}>
          Send test now
        </button>
      </div>
      {msg && <p className="mt-2 text-sm text-gray-600">{msg}</p>}
    </div>
  );
}

function ChildRow({ child, onView }) {
  return (
    <div className="flex items-center justify-between bg-white border border-gray-100 rounded-xl px-5 py-4 hover:shadow-sm transition-shadow">
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-full bg-brand-100 flex items-center justify-center font-bold text-brand-600">
          {child.student_id[0]?.toUpperCase()}
        </div>
        <div>
          <p className="font-semibold text-gray-900">{child.student_id}</p>
          <p className="text-xs text-gray-500">
            {child.topics_count} topics &bull; Last active: {child.last_active || 'N/A'}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-6">
        <div className="text-center">
          <p className="text-lg font-bold text-gray-900">{child.total_questions}</p>
          <p className="text-xs text-gray-500">Questions</p>
        </div>
        <div className="text-center">
          <p className={`text-lg font-bold ${child.accuracy >= 70 ? 'text-green-600' : child.accuracy >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
            {child.accuracy}%
          </p>
          <p className="text-xs text-gray-500">Accuracy</p>
        </div>
        <button onClick={() => onView(child.student_id)} className="btn-secondary text-sm flex items-center gap-1">
          <Eye size={14} /> View
        </button>
      </div>
    </div>
  );
}

function ChildDetailView({ studentId, onBack }) {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.guardianChildOverview(studentId)
      .then(setOverview)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [studentId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-brand-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!overview) {
    return <p className="text-gray-500">Could not load student data.</p>;
  }

  const { progress, knowledge_graph: kg } = overview;

  return (
    <div className="space-y-6">
      <button onClick={onBack} className="text-brand-600 flex items-center gap-1 text-sm hover:underline">
        <ChevronLeft size={16} /> Back to children
      </button>
      <h3 className="text-xl font-bold text-gray-900">{studentId}'s Progress</h3>

      <div className="grid grid-cols-3 gap-4">
        <div className="card text-center">
          <p className="text-2xl font-bold text-gray-900">{progress.total_questions}</p>
          <p className="text-sm text-gray-500">Questions</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-green-600">{progress.accuracy}%</p>
          <p className="text-sm text-gray-500">Accuracy</p>
        </div>
        <div className="card text-center">
          <p className="text-2xl font-bold text-brand-600">{Object.keys(progress.topics || {}).length}</p>
          <p className="text-sm text-gray-500">Topics</p>
        </div>
      </div>

      {Object.keys(progress.topics || {}).length > 0 && (
        <div className="card">
          <h4 className="font-semibold text-gray-900 mb-3">Topic Mastery</h4>
          <div className="space-y-3">
            {Object.entries(progress.topics)
              .sort(([, a], [, b]) => b - a)
              .map(([topic, val]) => {
                const pct = typeof val === 'number' ? (val <= 1 ? val * 100 : val) : 0;
                return (
                  <div key={topic} className="flex items-center gap-3">
                    <span className="text-sm font-medium w-36 truncate text-gray-700">{topic}</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${pct > 70 ? 'bg-green-500' : pct > 40 ? 'bg-amber-500' : 'bg-red-400'}`}
                        style={{ width: `${Math.max(5, pct)}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500 w-12 text-right">{pct.toFixed(0)}%</span>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {kg?.weak_links?.length > 0 && (
        <div className="card">
          <h4 className="font-semibold text-gray-900 mb-2">Weak Areas</h4>
          <div className="flex flex-wrap gap-2">
            {kg.weak_links.map((w, i) => (
              <span key={i} className="px-3 py-1 bg-red-50 text-red-700 rounded-full text-sm font-medium">{w}</span>
            ))}
          </div>
          {kg.suggested_focus && (
            <p className="mt-3 text-sm text-brand-600">{kg.suggested_focus}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function GuardianDashboard() {
  const { user } = useAuth();
  const [children, setChildren] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedChild, setSelectedChild] = useState(null);
  const [inviteCode, setInviteCode] = useState('');
  const [redeemMsg, setRedeemMsg] = useState('');

  const loadChildren = () => {
    setLoading(true);
    api.guardianChildren()
      .then(data => setChildren(data.children || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(loadChildren, []);

  const handleRedeem = async (e) => {
    e.preventDefault();
    if (!inviteCode.trim()) return;
    try {
      const data = await api.redeemGuardianInvite(inviteCode.trim());
      setRedeemMsg(data.message);
      setInviteCode('');
      loadChildren();
    } catch (err) {
      setRedeemMsg(err.message);
    }
  };

  if (selectedChild) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-8">
        <ChildDetailView studentId={selectedChild} onBack={() => setSelectedChild(null)} />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Users size={24} /> Guardian Dashboard
        </h2>
      </div>

      {/* Redeem invite code */}
      <div className="card">
        <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <KeyRound size={18} /> Redeem Invite Code
        </h3>
        <p className="text-sm text-gray-500 mb-3">Ask your child to generate an invite code from their account, then paste it here.</p>
        <form onSubmit={handleRedeem} className="flex gap-3">
          <input
            className="input-field flex-1"
            placeholder="Paste invite code"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value)}
          />
          <button type="submit" className="btn-primary text-sm">Redeem</button>
        </form>
        {redeemMsg && <p className="mt-2 text-sm text-green-600">{redeemMsg}</p>}
      </div>

      {/* B6: Weekly email digest */}
      <DigestCard />

      {loading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin h-8 w-8 border-4 border-brand-500 border-t-transparent rounded-full" />
        </div>
      ) : children.length === 0 ? (
        <div className="card text-center py-12">
          <Users size={48} className="mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-semibold text-gray-700 mb-2">No children linked</h3>
          <p className="text-gray-500">Redeem an invite code from your child to view their progress.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {children.map((c) => (
            <ChildRow key={c.student_id} child={c} onView={setSelectedChild} />
          ))}
        </div>
      )}
    </div>
  );
}
