/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // "Ink & Gilt" identity — champagne-gold signature accent (brand)
        // replaces the old indigo/violet AI palette.
        brand: {
          50: '#faf6ec', 100: '#f5edda', 200: '#ecdcb3', 300: '#e2c98c',
          400: '#d9b86e', 500: '#cfa654', 600: '#b98c3f', 700: '#97702f',
          800: '#775827', 900: '#5c4522',
        },
        // Ember — energy / streaks / rewards (distinct from brand gold)
        accent: {
          50: '#fdf3ec', 100: '#fbe3d3', 400: '#f08c4a', 500: '#e8732f', 600: '#d95f1d',
        },
        // Ink — deep blue-black graphite neutrals
        ink: {
          DEFAULT: '#1b2434', soft: '#3f4a5e', muted: '#65718a', faint: '#93a0b4',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'Arial', 'sans-serif'],
        display: ['Newsreader', 'Georgia', 'serif'],
      },
      borderRadius: {
        xl: '0.875rem', '2xl': '1.125rem', '3xl': '1.5rem',
      },
      boxShadow: {
        soft: '0 1px 2px rgba(13,17,27,0.04), 0 4px 16px rgba(13,17,27,0.06)',
        card: '0 1px 3px rgba(13,17,27,0.05), 0 8px 24px rgba(13,17,27,0.05)',
        pop: '0 8px 30px rgba(185,140,63,0.22)',
        'gold-glow': '0 0 0 1px rgba(217,184,110,0.28), 0 10px 40px -12px rgba(217,184,110,0.35)',
      },
      keyframes: {
        'fade-in': { '0%': { opacity: 0, transform: 'translateY(4px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        'scale-in': { '0%': { opacity: 0, transform: 'scale(0.97)' }, '100%': { opacity: 1, transform: 'scale(1)' } },
        'slide-up': { '0%': { opacity: 0, transform: 'translateY(12px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        shimmer: { '100%': { transform: 'translateX(100%)' } },
        'float-soft': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: 0.55 },
          '50%': { opacity: 1 },
        },
        'drift': {
          '0%, 100%': { transform: 'translate3d(0,0,0)' },
          '50%': { transform: 'translate3d(10px,-12px,0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.25s ease-out',
        'scale-in': 'scale-in 0.2s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
        'float-soft': 'float-soft 5s ease-in-out infinite',
        'pulse-soft': 'pulse-soft 3s ease-in-out infinite',
        'drift': 'drift 12s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}