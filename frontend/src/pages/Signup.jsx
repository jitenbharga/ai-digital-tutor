import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import { Eye, EyeOff, MailCheck } from 'lucide-react';
import Logo from '../components/Logo';
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
  const { login } = useAuth();
  const navigate = useNavigate();

  const onGoogle = (data) => {
    const role = data.role || 'student';
    login(data.username || '', data.access_token, role);
    navigate(role === 'guardian' ? '/guardian' : '/');
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
      await api.signup(username.trim(), password, accountType, dob, email.trim().toLowerCase());
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    setResendMsg('');
    try {
      await api.resendVerification(email.trim().toLowerCase());
      setResendMsg('Sent again. Check your inbox (and spam).');
    } catch (err) {
      setError(err.message);
    }
  };

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 to-indigo-50 px-4">
        <div className="card w-full max-w-md text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-green-100 rounded-2xl mb-4">
            <MailCheck className="text-green-600" size={28} />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Verify your email</h2>
          <p className="text-gray-500 mt-2">
            We sent a verification link to <span className="font-medium text-gray-700">{email}</span>.
            Click it to activate your account, then sign in.
          </p>
          {resendMsg && <p className="text-green-700 text-sm bg-green-50 p-3 rounded-lg mt-4">{resendMsg}</p>}
          <button onClick={resend} className="w-full text-sm font-medium text-brand-700 bg-brand-50 hover:bg-brand-100 rounded-lg py-2 mt-5 transition-colors">
            Resend verification email
          </button>
          <Link to="/login" className="btn-primary w-full mt-3 inline-block">Go to sign in</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 to-indigo-50 px-4">
      <div className="card w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex mb-4"><Logo size={56} className="rounded-2xl" /></div>
          <h2 className="text-2xl font-bold text-gray-900">Create account</h2>
          <p className="text-gray-500 mt-1">Start your AI-powered learning journey</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input className="input-field" value={username} onChange={e => setUsername(e.target.value)} required autoFocus />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input className="input-field" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <div className="relative">
              <input className="input-field pr-10" type={showPw ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} required />
              <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600" onClick={() => setShowPw(!showPw)}>
                {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm password</label>
            <input className="input-field" type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required />
          </div>
          {accountType === 'student' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Date of birth</label>
              <input className="input-field" type="date" value={dob} onChange={e => setDob(e.target.value)} required
                max={new Date().toISOString().split('T')[0]} />
              <p className="text-xs text-gray-400 mt-1">You must be 13 or older. Under 13? Ask a parent to create a guardian account.</p>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">I am a</label>
            <div className="flex gap-3">
              <button type="button"
                className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium border transition-colors ${
                  accountType === 'student' ? 'bg-brand-50 border-brand-500 text-brand-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
                onClick={() => setAccountType('student')}>
                Student
              </button>
              <button type="button"
                className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium border transition-colors ${
                  accountType === 'guardian' ? 'bg-brand-50 border-brand-500 text-brand-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
                onClick={() => setAccountType('guardian')}>
                Guardian
              </button>
            </div>
          </div>

          {error && <p className="text-red-600 text-sm bg-red-50 p-3 rounded-lg">{error}</p>}

          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        <div className="flex items-center gap-3 my-5">
          <div className="flex-1 h-px bg-gray-200" />
          <span className="text-xs text-gray-400">or</span>
          <div className="flex-1 h-px bg-gray-200" />
        </div>
        <GoogleButton accountType={accountType} onSuccess={onGoogle} onError={setError} />

        <p className="text-center text-sm text-gray-500 mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-brand-600 hover:text-brand-700 font-medium">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
