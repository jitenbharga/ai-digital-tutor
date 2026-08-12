import { useEffect, useRef } from 'react';
import { api } from '../lib/api';

/**
 * "Continue with Google" via Google Identity Services.
 * Presentational + API only — no auth context / router here (parent handles
 * login + navigation via onSuccess), so it can render on any page safely.
 * Renders nothing if VITE_GOOGLE_CLIENT_ID is not configured.
 */
const GSI_SRC = 'https://accounts.google.com/gsi/client';
let _gsiPromise = null;

function loadGsi() {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (_gsiPromise) return _gsiPromise;
  _gsiPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = GSI_SRC;
    s.async = true;
    s.defer = true;
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
  return _gsiPromise;
}

export default function GoogleButton({ onSuccess, onError, accountType = 'student' }) {
  const ref = useRef(null);
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;
    loadGsi()
      .then(() => {
        if (cancelled || !window.google?.accounts?.id || !ref.current) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async (resp) => {
            try {
              const data = await api.googleLogin(resp.credential, accountType);
              onSuccess?.(data);
            } catch (e) {
              onError?.(e.message || 'Google sign-in failed');
            }
          },
        });
        window.google.accounts.id.renderButton(ref.current, {
          theme: 'outline',
          size: 'large',
          text: 'continue_with',
          shape: 'pill',
          width: 320,
          logo_alignment: 'center',
        });
      })
      .catch(() => onError?.('Could not load Google sign-in'));
    return () => { cancelled = true; };
  }, [clientId]);

  if (!clientId) return null;
  return <div ref={ref} className="flex justify-center" />;
}
