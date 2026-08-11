/**
 * AI Tutor brand mark — indigo→violet rounded tile with a white "AI spark"
 * and a small orange accent spark (brand indigo + accent orange).
 * Self-contained SVG (matches /public/favicon.svg), crisp at any size.
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
          <stop stopColor="#6366F1" />
          <stop offset="1" stopColor="#4338CA" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="10" fill={`url(#${gid})`} />
      {/* main AI spark */}
      <path d="M20 6 L23.4 16.6 L34 20 L23.4 23.4 L20 34 L16.6 23.4 L6 20 L16.6 16.6 Z" fill="#ffffff" />
      {/* accent spark */}
      <path d="M29 7.5 L29.9 10.1 L32.5 11 L29.9 11.9 L29 14.5 L28.1 11.9 L25.5 11 L28.1 10.1 Z" fill="#F97316" />
    </svg>
  );
}
