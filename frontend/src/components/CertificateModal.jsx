import { useState } from 'react';
import { api } from '../lib/api';

const TIER_STYLES = {
  Proficiency: { gradient: 'from-blue-500 to-blue-600', accent: 'text-blue-400', star: 'text-blue-300' },
  Excellence:  { gradient: 'from-purple-500 to-purple-600', accent: 'text-purple-400', star: 'text-purple-300' },
  Mastery:     { gradient: 'from-amber-500 to-amber-600', accent: 'text-amber-400', star: 'text-amber-300' },
};

export default function CertificateModal({ certificate, onClose }) {
  const [downloading, setDownloading] = useState(false);

  if (!certificate) return null;

  const style = TIER_STYLES[certificate.tier] || TIER_STYLES.Proficiency;
  const pct = Math.round(certificate.mastery * 100);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const res = await api.downloadCertPdf(certificate.cert_id);
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `certificate_${certificate.topic}_${certificate.tier}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.message);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-gray-900 rounded-2xl border border-gray-700 p-8 max-w-md w-full mx-4 shadow-2xl animate-bounce-in">
        {/* Confetti-like decorations */}
        <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-4xl animate-pulse">
          {certificate.tier === 'Mastery' ? '👑' : certificate.tier === 'Excellence' ? '🌟' : '🎯'}
        </div>

        {/* Stars */}
        <div className={`text-center text-3xl mb-2 ${style.star}`}>
          ★ ★ ★
        </div>

        {/* Title */}
        <h2 className="text-center text-2xl font-bold text-white mb-1">
          Certificate Earned!
        </h2>
        <p className={`text-center text-sm font-medium mb-6 ${style.accent}`}>
          {certificate.tier} Level
        </p>

        {/* Certificate card */}
        <div className={`bg-gradient-to-br ${style.gradient} rounded-xl p-6 text-center text-white mb-6`}>
          <p className="text-sm opacity-80 mb-2">You have mastered</p>
          <h3 className="text-2xl font-bold capitalize mb-2">{certificate.topic}</h3>
          <div className="inline-flex items-center gap-2 bg-white/20 rounded-full px-4 py-1.5">
            <span className="text-lg font-bold">{pct}%</span>
            <span className="text-sm opacity-80">mastery</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="flex-1 px-4 py-2.5 bg-white text-gray-900 rounded-lg font-medium hover:bg-gray-100 transition-colors disabled:opacity-50"
          >
            {downloading ? 'Downloading...' : 'Download PDF'}
          </button>
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 bg-gray-700 text-white rounded-lg font-medium hover:bg-gray-600 transition-colors"
          >
            Continue
          </button>
        </div>
      </div>

      <style>{`
        @keyframes bounce-in {
          0% { transform: scale(0.8); opacity: 0; }
          50% { transform: scale(1.05); }
          100% { transform: scale(1); opacity: 1; }
        }
        .animate-bounce-in { animation: bounce-in 0.4s ease-out; }
      `}</style>
    </div>
  );
}
