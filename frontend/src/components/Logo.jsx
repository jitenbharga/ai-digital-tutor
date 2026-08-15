/**
 * AI Tutor brand mark — "Ink & Gilt" identity.
 * Gold tile with a dark "Learning Core" glyph: nucleus, knowledge orbits and
 * a teal node. Self-contained SVG (matches /public/favicon.svg), crisp at any size.
 */
export default function Logo({ size = 36, className = "", title = "AI Tutor" }) {
  const gid = "aiTutorBg";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label={title}
      className={className}
    >
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop stopColor="#ECD9A8" />
          <stop offset="0.55" stopColor="#D9B86E" />
          <stop offset="1" stopColor="#C29B47" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="10" fill={`url(#${gid})`} />
      {/* Learning Core glyph: ink nucleus + gold knowledge orbits + teal node */}
      <circle cx="20" cy="20" r="5" fill="#141A26" />
      <circle cx="20" cy="20" r="9.6" fill="none" stroke="#141A26" strokeOpacity="0.85" strokeWidth="2" />
      <circle cx="20" cy="20" r="13.6" fill="none" stroke="#141A26" strokeOpacity="0.35" strokeWidth="1.4" strokeDasharray="3.2 3.4" />
      <circle cx="30.5" cy="12.2" r="2.3" fill="#0E948A" />
    </svg>
  );
}