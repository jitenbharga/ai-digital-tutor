import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { BookOpen } from 'lucide-react';

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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 to-indigo-50 px-4">
      <div className="card w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-brand-100 rounded-xl mb-4">
            <BookOpen className="text-brand-600" size={28} />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Choose a new password</h2>
        </div>

        {!token ? (
          <p role="alert" className="text-center text-red-600 bg-red-50 p-4 rounded-lg">
            This reset link is invalid or missing. Request a new one.
          </p>
        ) : done ? (
          <p role="status" className="text-center text-gray-600 bg-green-50 p-4 rounded-lg">
            Password reset. Redirecting to sign in…
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="rp-password" className="block text-sm font-medium text-gray-700 mb-1">
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
              <label htmlFor="rp-confirm" className="block text-sm font-medium text-gray-700 mb-1">
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
            {error && <p className="text-red-600 text-sm bg-red-50 p-3 rounded-lg">{error}</p>}
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? 'Resetting…' : 'Reset password'}
            </button>
          </form>
        )}

        <p className="text-center text-sm text-gray-500 mt-6">
          <Link to="/login" className="text-brand-600 hover:text-brand-700 font-medium">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
