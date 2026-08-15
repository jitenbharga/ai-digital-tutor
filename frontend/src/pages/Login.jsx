import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import { sendEmailFrontend } from '../lib/emailService';
import { Eye, EyeOff } from 'lucide-react';
import AuthShell from '../components/AuthShell';
import GoogleButton from '../components/GoogleButton';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [needVerify, setNeedVerify] = useState(false);
  const [resendMsg, setResendMsg] = useState('');
  const [resendLink, setResendLink] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setNeedVerify(''); setResendMsg('');
    setLoading(true);
    try {
      const data = await api.login(email.trim().toLowerCase(), password);
      const role = data.role || 'student';
      login(data.username || email, data.access_token, role);
      const next = new URLSearchParams(window.location.search).get('next');
      const safeNext = next && next.startsWith('/') && !next.startsWith('//') ? next : null;
      navigate(safeNext || (role === 'guardian' ? '/guardian' : '/'));
    } catch (err) {
      if (err.message === 'email_not_verified') {
        setNeedVerify(true);
        setError('Please verify your email before signing in.');
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    setResendMsg(''); setError(''); setResendLink('');
    try {
      const data = await api.resendVerification(email.trim().toLowerCase());
      if (data?.link) {
        const result = await sendEmailFrontend({
          to_email: email.trim().toLowerCase(),
          recipient_name: 'User',
          subject: 'Verify your AI Tutor Account',
          message: `A fresh verification link has been created for your AI Tutor account.`,
          link: data.link,
          action_text: 'Verify Email',
        });
        setResendMsg(result.success
          ? 'Verification link sent. Check your inbox.'
          : result.simulated
            ? 'Email service is not configured — use the link below.'
            : 'We could not send the email right now — use the link below.');
        if (!result.success) setResendLink(data.link);
      } else {
        setResendMsg('If that account needs verification, a new link has been sent.');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const onGoogle = (data) => {
    const role = data.role || 'student';
    login(data.username || '', data.access_token, role);
    navigate(role === 'guardian' ? '/guardian' : '/');
  };

  return (
    <AuthShell>
      <div>
        <h2 className="font-display text-3xl font-medium tracking-tight text-ink">Welcome back</h2>
        <p className="text-[15px] text-ink-muted mt-1.5">Sign in to continue learning</p>
      </div>
      <div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="block text-sm font-medium text-ink-soft mb-1.5">Email</label>
            <input id="login-email" type="email" autoComplete="email" className="input-field" value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-sm font-medium text-ink-soft mb-1.5">Password</label>
            <div className="relative">
              <input id="login-password" className="input-field pr-10" type={showPw ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
              <button type="button" aria-label={showPw ? 'Hide password' : 'Show password'} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink-soft" onClick={() => setShowPw(!showPw)}>
                {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {error && <p className="text-red-600 text-sm bg-red-50 p-3 rounded-xl border border-red-200">{error}</p>}
          {needVerify && (
            <button type="button" onClick={resend} className="w-full text-sm font-medium text-brand-700 bg-brand-50 hover:bg-brand-100 rounded-xl py-2.5 transition-colors">
              Resend verification email
            </button>
          )}
          {resendMsg && <p className="text-green-700 text-sm bg-green-50 p-3 rounded-xl border border-green-200">{resendMsg}</p>}
          {resendLink && (
            <a href={resendLink} className="block text-sm font-medium text-brand-700 underline mt-2 break-all">
              Open verification link directly
            </a>
          )}

          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="flex items-center gap-3 my-5">
          <div className="flex-1 h-px" style={{ background: 'var(--bd)' }} />
          <span className="text-xs text-ink-faint">or</span>
          <div className="flex-1 h-px" style={{ background: 'var(--bd)' }} />
        </div>
        <GoogleButton onSuccess={onGoogle} onError={setError} />

        <p className="text-center text-sm text-ink-muted mt-6">
          <Link to="/forgot-password" className="text-brand-700 hover:text-brand-800 font-medium">Forgot password?</Link>
        </p>
        <p className="text-center text-sm text-ink-muted mt-2">
          Don't have an account?{' '}
          <Link to="/signup" className="text-brand-700 hover:text-brand-800 font-medium">Sign up</Link>
        </p>
      </div>
    </AuthShell>
  );
}