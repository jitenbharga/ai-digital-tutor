import Logo from './Logo';

/**
 * AuthShell — shared premium backdrop for all auth screens.
 * Atmospheric ink/paper depth with faint gold light, centered card.
 * Card content stays theme-aware via the global token system.
 */
export default function AuthShell({ children, wide = false }) {
  const [header, body] = Array.isArray(children) && children.length > 1 ? children : [null, children];
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10 relative overflow-hidden">
      {/* Atmospheric depth */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[760px] h-[480px] rounded-full"
          style={{ background: 'radial-gradient(closest-side, var(--gold-soft), transparent 70%)' }} />
        <div className="absolute -bottom-48 -right-24 w-[520px] h-[420px] rounded-full"
          style={{ background: 'radial-gradient(closest-side, var(--teal-soft), transparent 70%)' }} />
        <div className="absolute inset-0 bg-grid-ink opacity-60"
          style={{
            maskImage: 'radial-gradient(ellipse 80% 65% at 50% 40%, black, transparent 78%)',
            WebkitMaskImage: 'radial-gradient(ellipse 80% 65% at 50% 40%, black, transparent 78%)',
          }} />
      </div>

      <div className={`relative w-full ${wide ? 'max-w-md' : 'max-w-md'}`}>
        <div className="rounded-3xl border p-7 sm:p-9 shadow-card"
          style={{
            background: 'var(--glass)',
            borderColor: 'var(--bd)',
            backdropFilter: 'blur(20px) saturate(140%)',
            WebkitBackdropFilter: 'blur(20px) saturate(140%)',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,.06), 0 30px 70px -38px rgba(13,17,27,.5)',
          }}>
          <div className={`text-center ${header ? 'mb-8' : ''}`}>
            <div className="inline-flex mb-4 animate-float-soft"><Logo size={56} className="rounded-2xl" /></div>
            {header}
          </div>
          {body}
        </div>
      </div>
    </div>
  );
}