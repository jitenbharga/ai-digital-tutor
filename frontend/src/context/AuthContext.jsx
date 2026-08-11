import { createContext, useContext, useState, useEffect } from 'react';
import { setAccessToken, refreshAccessToken, api } from '../lib/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // SEC-5: no token in localStorage. On load, try to mint a fresh access
    // token from the httpOnly refresh cookie. username/role are non-secret
    // and kept in localStorage only for UX (avoids a flash of logged-out UI).
    let cancelled = false;
    (async () => {
      const username = localStorage.getItem('username');
      const role = localStorage.getItem('role') || 'student';
      const refreshed = await refreshAccessToken();
      if (!cancelled) {
        if (refreshed && username) {
          setUser({ username, token: refreshed.access_token, role: refreshed.role || role });
        }
        setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const login = (username, token, role = 'student') => {
    localStorage.setItem('username', username);
    localStorage.setItem('role', role);
    setAccessToken(token);
    setUser({ username, token, role });
  };

  const logout = () => {
    api.logout();
    setAccessToken(null);
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    // Legacy cleanup: remove any token left by an older build.
    localStorage.removeItem('token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
