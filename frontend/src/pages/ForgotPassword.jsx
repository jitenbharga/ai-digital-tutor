import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { sendPasswordResetEmail } from '../lib/emailService';
import { BookOpen } from 'lucide-react';

export default function ForgotPassword() {
  const [identifier, setIdentifier] = useState('');
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fallbackLink, setFallbackLink] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    // Response is intentionally generic (no account enumeration), so we show the
    // same confirmation regardless of the outcome.
    try {
      const data = await api.forgotPassword(identifier);
      if (data?.link) {
        const result = await sendPasswordResetEmail(identifier, '', data.link);
        if (!result.success) setFallbackLink(data.link);
      }
    } catch {
      /* ignore — never reveal whether the account exists */
    }
    setSent(true);
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 to-indigo-50 px-4">
      <div className="card w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-brand-100 rounded-xl mb-4">
            <BookOpen className="text-brand-600" size={28} />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Reset your password</h2>
          <p className="text-gray-500 mt-1">We&apos;ll email a reset link if an account exists.</p>
        </div>

        {sent ? (
          <>
            <p role="status" className="text-center text-gray-600 bg-green-50 p-4 rounded-lg">
              If a matching account with an email exists, a reset link has been sent.
              Check your inbox.
            </p>
            {fallbackLink && (
              <a href={fallbackLink} className="block text-sm font-medium text-brand-700 underline mt-3 text-center break-all">
                Open reset link directly
              </a>
            )}
          </>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="fp-identifier" className="block text-sm font-medium text-gray-700 mb-1">
                Username or email
              </label>
              <input
                id="fp-identifier"
                className="input-field"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                required
                autoFocus
              />
            </div>
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? 'Sending…' : 'Send reset link'}
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
