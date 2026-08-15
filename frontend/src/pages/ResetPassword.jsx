import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { BookOpen } from 'lucide-react';
import AuthShell from '../components/AuthShell';

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const [pw, setPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (pw.length < 8) return setError('Password must be at least 8 characters');
    if (pw !== confirm) return setError('Passwords do not match');
    setLoading(true);
    try {
      await api.resetPassword(token, pw);
      setDone(true);
      setTimeout(() => navigate('/login'), 1600);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell>
      <div>
        <div className="inline-flex items-center justify-center w-14 h-14 bg-brand-50 rounded-xl mb-4">
          <BookOpen className="text-brand-600" size={28} />
        </div>
        <h2 className="font-display text-3xl font-medium tracking-tight text-ink">Choose a new password</h2>
      </div>
      <div>
        {!token ? (
          <p role="alert" className="text-center text-red-600 bg-red-50 border border-red-200 p-4 rounded-xl">
            This reset link is invalid or missing. Request a new one.
          </p>
        ) : done ? (
          <p role="status" className="text-center text-ink-muted bg-green-50 border border-green-200 p-4 rounded-xl">
            Password reset. Redirecting to sign in…
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="rp-password" className="block text-sm font-medium text-ink-soft mb-1.5">
                New password
              </label>
              <input
                id="rp-password"
                type="password"
                className="input-field"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div>
              <label htmlFor="rp-confirm" className="block text-sm font-medium text-ink-soft mb-1.5">
                Confirm password
              </label>
              <input
                id="rp-confirm"
                type="password"
                className="input-field"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-red-600 text-sm bg-red-50 p-3 rounded-xl border border-red-200">{error}</p>}
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? 'Resetting…' : 'Reset password'}
            </button>
          </form>
        )}

        <p className="text-center text-sm text-ink-muted mt-6">
          <Link to="/login" className="text-brand-700 hover:text-brand-800 font-medium">
            Back to sign in
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}