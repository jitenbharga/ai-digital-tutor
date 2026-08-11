import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import { Eye, EyeOff } from 'lucide-react';
import Logo from '../components/Logo';
import GoogleButton from '../components/GoogleButton';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [needVerify, setNeedVerify] = useState(false);
  const [resendMsg, setResendMsg] = useState('');
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
    setResendMsg(''); setError('');
    try {
      await api.resendVerification(email.trim().toLowerCase());
      setResendMsg('Verification link sent. Check your inbox.');
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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 to-indigo-50 px-4">
      <div className="card w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex mb-4"><Logo size={56} className="rounded-2xl" /></div>
          <h2 className="text-2xl font-bold text-gray-900">Welcome back</h2>
          <p className="text-gray-500 mt-1">Sign in to continue learning</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input id="login-email" type="email" autoComplete="email" className="input-field" value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <div className="relative">
              <input id="login-password" className="input-field pr-10" type={showPw ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
              <button type="button" aria-label={showPw ? 'Hide password' : 'Show password'} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600" onClick={() => setShowPw(!showPw)}>
                {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {error && <p className="text-red-600 text-sm bg-red-50 p-3 rounded-lg">{error}</p>}
          {needVerify && (
            <button type="button" onClick={resend} className="w-full text-sm font-medium text-brand-700 bg-brand-50 hover:bg-brand-100 rounded-lg py-2 transition-colors">
              Resend verification email
            </button>
          )}
          {resendMsg && <p className="text-green-700 text-sm bg-green-50 p-3 rounded-lg">{resendMsg}</p>}

          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="flex items-center gap-3 my-5">
          <div className="flex-1 h-px bg-gray-200" />
          <span className="text-xs text-gray-400">or</span>
          <div className="flex-1 h-px bg-gray-200" />
        </div>
        <GoogleButton onSuccess={onGoogle} onError={setError} />

        <p className="text-center text-sm text-gray-500 mt-6">
          <Link to="/forgot-password" className="text-brand-600 hover:text-brand-700 font-medium">Forgot password?</Link>
        </p>
        <p className="text-center text-sm text-gray-500 mt-2">
          Don't have an account?{' '}
          <Link to="/signup" className="text-brand-600 hover:text-brand-700 font-medium">Sign up</Link>
        </p>
      </div>
    </div>
  );
}
