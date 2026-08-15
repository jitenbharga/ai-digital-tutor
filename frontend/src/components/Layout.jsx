import { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { usePreferences } from '../context/PreferencesContext';
import { api } from '../lib/api';
import { Home, BookOpen, RefreshCw, BarChart3, LogOut, Users, Settings, MessageCircleQuestion, Sun, Moon } from 'lucide-react';
import NotificationBell from './NotificationBell';
import Logo from './Logo';
import { useSmartNudges } from '../hooks/useSmartNudges';
import { useTheme } from '../hooks/useTheme';
import PageTransition from './motion/PageTransition';

export default function Layout() {
  const { user, logout } = useAuth();
  const { t } = usePreferences();
  const { isDark, toggle: toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [reviewDueCount, setReviewDueCount] = useState(0);

  // Feature #5: fire opt-in browser study nudges (exam near / reviews due)
  useSmartNudges();

  const handleLogout = () => { logout(); navigate('/login'); };

  // N4: Fetch review-due count for badge
  useEffect(() => {
    api.getReviewDueCount()
      .then(data => setReviewDueCount(data?.count || 0))
      .catch(() => {});
  }, [location.pathname]);

  // Hide bottom nav on tutor and ask pages (they have their own headers)
  const hideTabs = location.pathname === '/tutor' || location.pathname === '/ask' || location.pathname.startsWith('/curriculum/');

  // Bottom-nav tab (mobile)
  const tab = (to, label, Icon) => (
    <NavLink to={to} end aria-label={label}
      className={({ isActive }) =>
        `flex flex-col items-center gap-1 flex-1 min-w-0 max-w-[88px] px-1.5 py-2 rounded-xl transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
          isActive ? 'text-brand-700 bg-brand-50' : 'text-ink-faint hover:text-ink-soft'
        }`
      }>
      <Icon size={22} aria-hidden="true" />
      <span className="text-[11px] font-medium leading-none truncate max-w-full">{label}</span>
    </NavLink>
  );

  // Sidebar item (desktop)
  const sideItem = (to, label, Icon, badge = 0) => (
    <NavLink to={to} end aria-label={label}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 relative focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
          isActive ? 'bg-brand-50/80 text-brand-700 shadow-sm' : 'text-ink-soft hover:bg-white/5'
        }`
      }>
      {({ isActive }) => (
        <>
          {isActive && <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-full" style={{ background: 'var(--gold)' }} />}
          <Icon size={20} className={isActive ? 'text-brand-600' : 'text-ink-faint'} aria-hidden="true" />
          <span>{label}</span>
          {badge > 0 && (
            <span className="ml-auto min-w-[18px] h-[18px] bg-amber-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">
              {badge > 9 ? '9+' : badge}
            </span>
          )}
        </>
      )}
    </NavLink>
  );

  return (
    <div className="min-h-screen lg:flex">
      <a href="#main-content" className="skip-link">Skip to content</a>

      {/* Desktop sidebar (lg+) — hidden on immersive pages (tutor/ask/curriculum) */}
      {!hideTabs && (
      <aside className="hidden lg:flex lg:flex-col lg:w-64 lg:shrink-0 sticky top-0 h-screen border-r bg-white/70 dark:bg-[#0b0f18]/80 backdrop-blur-xl"
        style={{ borderColor: 'var(--bd)' }}>
        <button onClick={() => navigate('/')} className="flex items-center gap-2.5 px-5 h-16 border-b shrink-0 group cursor-pointer"
          style={{ borderColor: 'var(--bd2)' }}>
          <Logo size={36} className="rounded-xl transition-shadow duration-300 group-hover:shadow-gold-glow" />
          <span className="font-display text-[22px] font-medium text-ink tracking-tight">AI&nbsp;Tutor</span>
        </button>

        <nav className="flex-1 overflow-y-auto p-3 space-y-1" aria-label="Main navigation">
          {sideItem('/', t('home'), Home)}
          {sideItem('/ask', 'Ask', MessageCircleQuestion)}
          {sideItem('/learn', t('learn'), BookOpen)}
          {sideItem('/review', t('review'), RefreshCw, reviewDueCount)}
          {sideItem('/progress', t('progress'), BarChart3)}
          {user?.role === 'guardian' && sideItem('/guardian', 'Children', Users)}
        </nav>

        <div className="p-3 border-t space-y-1 shrink-0" style={{ borderColor: 'var(--bd2)' }}>
          <button onClick={toggleTheme}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-ink-soft hover:bg-white/5 transition-colors cursor-pointer">
            {isDark ? <Sun size={20} className="text-ink-faint" /> : <Moon size={20} className="text-ink-faint" />}
            {isDark ? 'Light mode' : 'Dark mode'}
          </button>
          {sideItem('/settings', t('settings'), Settings)}
          <div className="flex items-center gap-1.5 pt-2">
            <button onClick={() => navigate('/profile')}
              className="flex items-center gap-2.5 min-w-0 flex-1 hover:bg-white/5 rounded-lg px-2 py-1.5 transition-colors text-left cursor-pointer"
              title="View profile">
              <span className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 text-[#201a0e]"
                style={{ background: 'linear-gradient(180deg,#ecd9a8,#cfa654)' }}>
                {(user?.username || '?')[0]?.toUpperCase()}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-ink truncate">{user?.username}</p>
                <p className="text-[11px] text-ink-muted capitalize">{user?.role || 'student'}</p>
              </div>
            </button>
            {user?.role !== 'guardian' && <NotificationBell />}
            <button onClick={handleLogout} title={t('logout')}
              className="text-ink-faint hover:text-red-500 hover:bg-red-500/10 p-2 rounded-lg transition-colors flex-shrink-0 cursor-pointer">
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>
      )}

      {/* Content column */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        {/* Mobile top bar — hidden on desktop (everything moved to sidebar) */}
        <header className="lg:hidden sticky top-0 z-40 px-4 sm:px-6 py-2.5 flex items-center justify-between bg-white/80 dark:bg-[#0a0e16]/80 backdrop-blur-xl border-b"
          style={{ borderColor: 'var(--bd)' }}>
          <button className="flex items-center gap-2 cursor-pointer group" onClick={() => navigate('/')}>
            <Logo size={32} className="rounded-xl transition-shadow duration-300 group-hover:shadow-gold-glow" />
            <span className="font-display text-xl font-medium text-ink tracking-tight">AI&nbsp;Tutor</span>
          </button>
          <div className="flex items-center gap-1.5 sm:gap-2.5">
            {user?.role === 'guardian' && (
              <NavLink to="/guardian" className="text-ink-faint hover:text-brand-600 hover:bg-brand-50 p-2 rounded-lg transition-colors" title="Children">
                <Users size={18} />
              </NavLink>
            )}
            <button onClick={() => navigate('/profile')} className="text-sm font-medium text-ink-muted hover:text-brand-600 hidden sm:inline mr-1 transition-colors cursor-pointer">{user?.username}</button>
            {user?.role !== 'guardian' && <NotificationBell />}
            <button onClick={toggleTheme} className="text-ink-faint hover:text-brand-600 hover:bg-brand-50 p-2 rounded-lg transition-colors cursor-pointer" title={isDark ? 'Light mode' : 'Dark mode'}>
              {isDark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <NavLink to="/settings" className="text-ink-faint hover:text-brand-600 hover:bg-brand-50 p-2 rounded-lg transition-colors" title={t('settings')}>
              <Settings size={18} />
            </NavLink>
            <button onClick={handleLogout} className="text-ink-faint hover:text-red-500 hover:bg-red-500/10 p-2 rounded-lg transition-colors cursor-pointer" title={t('logout')}>
              <LogOut size={18} />
            </button>
          </div>
        </header>

        {/* Page content with gentle route transitions */}
        <main id="main-content" className={`flex-1 overflow-auto ${hideTabs ? '' : 'pb-24 lg:pb-0'}`} role="main">
          <PageTransition key={location.pathname}>
            <Outlet />
          </PageTransition>
        </main>
      </div>

      {/* Bottom tab bar — mobile only, floating premium pill */}
      {!hideTabs && (
        <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 flex justify-center px-4 pb-3 safe-bottom pointer-events-none" role="navigation" aria-label="Main navigation">
          <div className="pointer-events-auto flex justify-center gap-0.5 sm:gap-1 px-2 sm:px-3 py-1.5 rounded-2xl border bg-white/85 dark:bg-[#10151f]/85 backdrop-blur-xl max-w-md w-full"
            style={{ borderColor: 'var(--bd)', boxShadow: '0 18px 44px -18px rgba(13,17,27,.35)' }}>
            {tab('/', t('home'), Home)}
            {tab('/ask', 'Ask', MessageCircleQuestion)}
            {tab('/learn', t('learn'), BookOpen)}
            <NavLink to="/review" end aria-label={t('review')}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 flex-1 min-w-0 max-w-[88px] px-1.5 py-2 rounded-xl transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 relative ${
                  isActive ? 'text-brand-700 bg-brand-50' : 'text-ink-faint hover:text-ink-soft'
                }`
              }>
              <RefreshCw size={22} aria-hidden="true" />
              <span className="text-[11px] font-medium leading-none truncate max-w-full">{t('review')}</span>
              {reviewDueCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] bg-amber-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">
                  {reviewDueCount > 9 ? '9+' : reviewDueCount}
                </span>
              )}
            </NavLink>
            {tab('/progress', t('progress'), BarChart3)}
          </div>
        </nav>
      )}

      <style>{`
        .safe-bottom { padding-bottom: max(6px, env(safe-area-inset-bottom)); }
      `}</style>
    </div>
  );
}