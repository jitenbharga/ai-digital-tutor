import { useEffect, useState } from 'react';

const COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899'];

function randomBetween(a, b) {
  return Math.random() * (b - a) + a;
}

export default function Confetti({ duration = 3000, pieces = 60, onDone }) {
  const [particles, setParticles] = useState([]);

  useEffect(() => {
    const ps = Array.from({ length: pieces }, (_, i) => ({
      id: i,
      x: randomBetween(5, 95),
      delay: randomBetween(0, 0.5),
      duration: randomBetween(1.5, 3),
      color: COLORS[i % COLORS.length],
      size: randomBetween(6, 12),
      rotation: randomBetween(0, 360),
      drift: randomBetween(-30, 30),
    }));
    setParticles(ps);

    const timer = setTimeout(() => {
      setParticles([]);
      onDone?.();
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, pieces, onDone]);

  if (particles.length === 0) return null;

  return (
    <div className="fixed inset-0 pointer-events-none z-[9999] overflow-hidden">
      {particles.map(p => (
        <div
          key={p.id}
          className="absolute"
          style={{
            left: `${p.x}%`,
            top: '-2%',
            width: p.size,
            height: p.size * 0.6,
            backgroundColor: p.color,
            borderRadius: '2px',
            transform: `rotate(${p.rotation}deg)`,
            animation: `confetti-fall ${p.duration}s ease-in ${p.delay}s forwards`,
          }}
        />
      ))}
      <style>{`
        @keyframes confetti-fall {
          0% { transform: translateY(0) rotate(0deg); opacity: 1; }
          100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
