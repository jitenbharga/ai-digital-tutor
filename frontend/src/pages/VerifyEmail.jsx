import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import AuthShell from '../components/AuthShell';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const [status, setStatus] = useState('loading'); // loading | ok | error
  const [msg, setMsg] = useState('');

  // The verify token is single-use. React 18 StrictMode runs effects twice in
  // dev, which would fire the request twice — the first consumes the token, the
  // second then fails as "invalid/expired". This ref ensures we send it once.
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const token = params.get('token');
    if (!token) {
      setStatus('error');
      setMsg('Missing verification token.');
      return;
    }
    api.verifyEmail(token)
      .then(() => { setStatus('ok'); setMsg('Your email is verified — you can sign in now.'); })
      .catch((e) => { setStatus('error'); setMsg(e.message || 'Invalid or expired verification link.'); });
  }, [params]);

  return (
    <AuthShell>
      <div className="flex flex-col items-center gap-1">
        {status === 'loading' && (
          <>
            <Loader2 className="text-brand-600 animate-spin" size={32} />
            <p className="text-ink-muted mt-4">Verifying your email…</p>
          </>
        )}
        {status === 'ok' && (
          <>
            <CheckCircle2 className="text-green-600" size={40} />
            <h2 className="font-display text-3xl font-medium tracking-tight text-ink mt-3">Email verified</h2>
            <p className="text-ink-muted mt-1">{msg}</p>
            <Link to="/login" className="btn-primary w-full mt-6 inline-block">Sign in</Link>
          </>
        )}
        {status === 'error' && (
          <>
            <XCircle className="text-red-500" size={40} />
            <h2 className="font-display text-3xl font-medium tracking-tight text-ink mt-3">Verification failed</h2>
            <p className="text-ink-muted mt-1">{msg}</p>
            <Link to="/login" className="btn-secondary w-full mt-6 inline-block">Back to sign in</Link>
          </>
        )}
      </div>
    </AuthShell>
  );
}