import { useState, useEffect, useCallback } from 'react';

const KEY = 'theme';

/** Apply the saved theme to <html> as early as possible (avoids a flash). */
export function applyThemeFromStorage() {
  try {
    const t = localStorage.getItem(KEY) || 'dark';
    document.documentElement.classList.toggle('dark', t === 'dark');
  } catch { /* no storage */ }
}

/** Light/dark theme state, persisted to localStorage and reflected on <html>. */
export function useTheme() {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem(KEY) || 'dark'; } catch { return 'light'; }
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    try { localStorage.setItem(KEY, theme); } catch { /* no storage */ }
  }, [theme]);

  const toggle = useCallback(() => setTheme(t => (t === 'dark' ? 'light' : 'dark')), []);
  return { theme, setTheme, toggle, isDark: theme === 'dark' };
}
