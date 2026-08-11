import { createContext, useContext, useState, useCallback } from 'react';
import Confetti from './Confetti';
import LevelUpModal from './LevelUpModal';

const CelebrationContext = createContext(null);

export function CelebrationProvider({ children }) {
  const [confetti, setConfetti] = useState(false);
  const [levelUp, setLevelUp] = useState(null);
  const [badgeToast, setBadgeToast] = useState(null);

  const celebrate = useCallback((celebrations) => {
    if (!celebrations || !Array.isArray(celebrations)) return;

    for (const c of celebrations) {
      if (c.event === 'daily_goal_completed') {
        setConfetti(true);
      }
      if (c.event === 'level_up' && c.new_level) {
        setLevelUp(c.new_level);
        setConfetti(true);
      }
      if (c.event === 'badge_unlocked' && c.new_badges?.length) {
        const badge = c.new_badges[0];
        setBadgeToast(badge);
        setTimeout(() => setBadgeToast(null), 4000);
      }
    }
  }, []);

  return (
    <CelebrationContext.Provider value={{ celebrate }}>
      {children}

      {confetti && <Confetti onDone={() => setConfetti(false)} />}

      {levelUp && (
        <LevelUpModal level={levelUp} onClose={() => setLevelUp(null)} />
      )}

      {badgeToast && (
        <div className="fixed top-4 right-4 left-4 sm:left-auto z-[9997] animate-slide-in">
          <div className="bg-white rounded-2xl shadow-xl border border-gray-200 px-5 py-4 flex items-center gap-3 max-w-xs sm:ml-auto">
            <span className="text-3xl">{badgeToast.emoji}</span>
            <div>
              <p className="font-bold text-gray-900 text-sm">Badge unlocked!</p>
              <p className="text-gray-600 text-xs">{badgeToast.name} — {badgeToast.description}</p>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes slide-in {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        .animate-slide-in { animation: slide-in 0.3s ease-out; }
      `}</style>
    </CelebrationContext.Provider>
  );
}

export function useCelebration() {
  const ctx = useContext(CelebrationContext);
  if (!ctx) throw new Error('useCelebration must be inside CelebrationProvider');
  return ctx;
}
