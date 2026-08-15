import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import { sendVerificationEmail } from '../lib/emailService';
import { Eye, EyeOff, MailCheck } from 'lucide-react';
import AuthShell from '../components/AuthShell';
import GoogleButton from '../components/GoogleButton';

export default function Signup() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [accountType, setAccountType] = useState('student');
  const [dob, setDob] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);   // show "check your email" screen
  const [resendMsg, setResendMsg] = useState('');
  const [emailFallback, setEmailFallback] = useState(''); // link shown if email service is unconfigured
  const { login } = useAuth();
  const navigate = useNavigate();

  const onGoogle = (data) => {
    const role = data.role || 'student';
    login(data.username || '', data.access_token, role);
    navigate(role === 'guardian' ? '/guardian' : '/');
  };

  const emailVerification = async (toEmail, link) => {
    if (!link) return;
    try {
      const result = await sendVerificationEmail(toEmail, username, link);
      if (!result.success) {
        setEmailFallback(link);
        setResendMsg(result.simulated
          ? 'Email service is not configured — use the link below to verify your email.'
          : 'We could not send the verification email right now — use the link below.');
      } else {
        setEmailFallback('');
        setResendMsg('');
      }
    } catch {
      setEmailFallback(link);
      setResendMsg('We could not send the verification email right now — use the link below.');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) { setError('Passwords do not match'); return; }
    if (password.length < 8) { setError('Password must be at least 8 characters'); return; }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { setError('Enter a valid email'); return; }
    if (accountType === 'student' && !dob) { setError('Please enter your date of birth'); return; }
    setLoading(true);
    try {
      const data = await api.signup(username.trim(), password, accountType, dob, email.trim().toLowerCase());
      setDone(true);
      await emailVerification(email.trim().toLowerCase(), data?.verify_link);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    setResendMsg('');
    try {
      const data = await api.resendVerification(email.trim().toLowerCase());
      setResendMsg('Sent again. Check your inbox (and spam).');
      await emailVerification(email.trim().toLowerCase(), data?.link);
    } catch (err) {
      setError(err.message);
    }
  };

  if (done) {
    return (
      <AuthShell>
        <div className="inline-flex items-center justify-center w-14 h-14 bg-green-100 rounded-2xl mb-4">
          <MailCheck className="text-green-600" size={28} />
        </div>
        <h2 className="font-display text-3xl font-medium tracking-tight text-ink">Verify your email</h2>
        <p className="text-ink-muted mt-2">
          We sent a verification link to <span className="font-medium text-ink-soft">{email}</span>.
          Click it to activate your account, then sign in.
        </p>
        <div>
          {resendMsg && <p className="text-green-700 text-sm bg-green-50 p-3 rounded-xl border border-green-200 mt-2">{resendMsg}</p>}
          {emailFallback && (
            <a href={emailFallback} className="block text-sm font-medium text-brand-700 underline mt-2 break-all">
              Open verification link directly
            </a>
          )}
          <button onClick={resend} className="w-full text-sm font-medium text-brand-700 bg-brand-50 hover:bg-brand-100 rounded-xl py-2.5 mt-5 transition-colors">
            Resend verification email
          </button>
          <Link to="/login" className="btn-primary w-full mt-3 inline-block">Go to sign in</Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <div>
        <h2 className="font-display text-3xl font-medium tracking-tight text-ink">Create account</h2>
        <p className="text-ink-muted mt-1.5">Start your AI-powered learning journey</p>
      </div>
      <div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-1.5">Username</label>
            <input className="input-field" value={username} onChange={e => setUsername(e.target.value)} required autoFocus />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-1.5">Email</label>
            <input className="input-field" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-1.5">Password</label>
            <div className="relative">
              <input className="input-field pr-10" type={showPw ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} required />
              <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink-soft" onClick={() => setShowPw(!showPw)}>
                {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-1.5">Confirm password</label>
            <input className="input-field" type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required />
          </div>
          {accountType === 'student' && (
            <div>
              <label className="block text-sm font-medium text-ink-soft mb-1.5">Date of birth</label>
              <input className="input-field" type="date" value={dob} onChange={e => setDob(e.target.value)} required
                max={new Date().toISOString().split('T')[0]} />
              <p className="text-xs text-ink-faint mt-1">You must be 13 or older. Under 13? Ask a parent to create a guardian account.</p>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-1.5">I am a</label>
            <div className="flex gap-3">
              <button type="button"
                className={`flex-1 py-2 px-3 rounded-xl text-sm font-medium border transition-colors ${
                  accountType === 'student' ? 'bg-brand-50 border-brand-500 text-brand-700' : 'border-ink-faint/30 text-ink-muted hover:bg-brand-50/40'
                }`}
                onClick={() => setAccountType('student')}>
                Student
              </button>
              <button type="button"
                className={`flex-1 py-2 px-3 rounded-xl text-sm font-medium border transition-colors ${
                  accountType === 'guardian' ? 'bg-brand-50 border-brand-500 text-brand-700' : 'border-ink-faint/30 text-ink-muted hover:bg-brand-50/40'
                }`}
                onClick={() => setAccountType('guardian')}>
                Guardian
              </button>
            </div>
          </div>

          {error && <p className="text-red-600 text-sm bg-red-50 p-3 rounded-xl border border-red-200">{error}</p>}

          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        <div className="flex items-center gap-3 my-5">
          <div className="flex-1 h-px" style={{ background: 'var(--bd)' }} />
          <span className="text-xs text-ink-faint">or</span>
          <div className="flex-1 h-px" style={{ background: 'var(--bd)' }} />
        </div>
        <GoogleButton accountType={accountType} onSuccess={onGoogle} onError={setError} />

        <p className="text-center text-sm text-ink-muted mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-brand-700 hover:text-brand-800 font-medium">Sign in</Link>
        </p>
      </div>
    </AuthShell>
  );
}
