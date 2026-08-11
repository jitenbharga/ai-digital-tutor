import { useEffect } from 'react';
import { Trophy, X } from 'lucide-react';

export default function LevelUpModal({ level, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 5000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[9998] animate-fade-in">
      <div className="bg-white rounded-3xl p-8 max-w-sm mx-4 text-center shadow-2xl relative animate-bounce-in">
        <button onClick={onClose} className="absolute top-3 right-3 text-gray-300 hover:text-gray-500">
          <X size={20} />
        </button>

        <div className="w-20 h-20 mx-auto mb-4 bg-gradient-to-br from-amber-400 to-orange-500 rounded-full flex items-center justify-center shadow-lg">
          <Trophy size={40} className="text-white" />
        </div>

        <h2 className="text-2xl font-bold text-gray-900 mb-1">Level Up!</h2>
        <p className="text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-brand-600 to-purple-600 mb-2">
          {level}
        </p>
        <p className="text-gray-500 text-sm">
          You're making amazing progress. Keep it up!
        </p>
      </div>

      <style>{`
        @keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
        @keyframes bounce-in {
          0% { transform: scale(0.3); opacity: 0; }
          50% { transform: scale(1.05); }
          70% { transform: scale(0.95); }
          100% { transform: scale(1); opacity: 1; }
        }
        .animate-fade-in { animation: fade-in 0.2s ease-out; }
        .animate-bounce-in { animation: bounce-in 0.5s ease-out; }
      `}</style>
    </div>
  );
}
