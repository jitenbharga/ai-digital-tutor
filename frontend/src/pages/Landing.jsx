import { lazy, Suspense } from 'react';
import { useNavigate } from 'react-router-dom';
import Logo from '../components/Logo';
import Reveal from '../components/motion/Reveal';
import Stagger from '../components/motion/Stagger';

const LearningCore = lazy(() => import('../components/3d/LearningCore'));

const FEATURES = [
  { glyph: '◉', tint: 'gold', t: 'Adaptive AI tutoring', d: 'Lessons that read your level and move between direct teaching and Socratic questioning as you go.' },
  { glyph: '◈', tint: 'teal', t: 'Practice your weak spots', d: 'One tap builds a targeted set from the exact questions and concepts you keep getting wrong.' },
  { glyph: '◱', tint: 'gold', t: 'Exam-ready plans', d: 'A day-by-day plan to your exam date with a live readiness meter, so you always know where you stand.' },
  { glyph: '❖', tint: 'teal', t: 'Learn by explaining', d: 'Explain a topic back in your own words and get graded — the fastest way to make it stick.' },
  { glyph: '✎', tint: 'gold', t: 'Step-by-step solver', d: 'Write your working by hand; the tutor checks each step and nudges you the moment you slip.' },
  { glyph: '▤', tint: 'teal', t: 'Flashcards, offline', d: 'Cards build themselves from your mistakes and sync your reviews even without a connection.' },
];

const GLYPH_STYLE = {
  gold: {
    box: 'bg-[#d9b86e]/10 border-[#d9b86e]/25 text-[#ecd9a8]',
    hover: 'hover:border-[#d9b86e]/50',
  },
  teal: {
    box: 'bg-[#5fd9ce]/10 border-[#5fd9ce]/25 text-[#7fe3da]',
    hover: 'hover:border-[#5fd9ce]/45',
  },
};

function HeroScene() {
  return (
    <div className="relative w-full h-[320px] sm:h-[400px] lg:h-[560px]" aria-hidden="true">
      {/* Suspense fallback: quiet static glow while the WebGL module loads */}
      <Suspense fallback={
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-56 h-56 rounded-full opacity-60"
            style={{ background: 'radial-gradient(closest-side, rgba(217,184,110,.18), transparent 70%)' }} />
        </div>
      }>
        <LearningCore className="absolute inset-0" />
      </Suspense>
      {/* Soft grounding glow behind the core */}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[420px] h-[420px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(closest-side, rgba(217,184,110,.07), transparent 68%)' }} />
    </div>
  );
}

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="relative min-h-screen overflow-x-hidden font-sans text-[#eef1f6]" style={{ background: '#070a10' }}>
      {/* Atmospheric background */}
      <div className="fixed inset-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(1000px 640px at 50% -16%, rgba(217,184,110,.13), transparent 60%),' +
            'radial-gradient(760px 560px at 88% 6%, rgba(95,217,206,.07), transparent 58%),' +
            'radial-gradient(760px 640px at 4% 36%, rgba(185,140,63,.06), transparent 60%),' +
            'linear-gradient(180deg,#080b12,#06080e 70%)',
        }}
      />
      <div className="fixed inset-0 pointer-events-none bg-grid-ink opacity-[0.35]" style={{
        maskImage: 'radial-gradient(ellipse 90% 70% at 50% 0%, black, transparent 75%)',
        WebkitMaskImage: 'radial-gradient(ellipse 90% 70% at 50% 0%, black, transparent 75%)',
      }} />

      <div className="relative z-10">
        {/* Sticky glass nav */}
        <nav className="sticky top-0 z-20">
          <div className="mx-auto max-w-6xl px-5 sm:px-8 pt-4">
            <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.045] px-4 sm:px-6 py-3 backdrop-blur-xl"
              style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,.07), 0 14px 44px -22px rgba(0,0,0,.8)' }}>
              <button className="flex items-center gap-2.5 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
                <Logo size={34} />
                <span className="font-display text-xl font-medium tracking-tight text-[#f2f4f8]">AI Tutor</span>
              </button>
              <div className="hidden md:flex items-center gap-8 text-sm text-[#98a2b8]">
                <a href="#features" className="hover:text-[#eef1f6] transition-colors">Features</a>
                <a href="#how" className="hover:text-[#eef1f6] transition-colors">How it works</a>
                <a href="#start" className="hover:text-[#eef1f6] transition-colors">Get started</a>
              </div>
              <div className="flex items-center gap-3">
                <button onClick={() => navigate('/login')} className="text-sm font-medium text-[#aab4c4] hover:text-[#eef1f6] transition-colors px-2 py-1.5 cursor-pointer">
                  Sign in
                </button>
                <button onClick={() => navigate('/signup')}
                  className="text-sm font-semibold rounded-xl px-4 py-2 text-[#201a0e] cursor-pointer transition-all duration-150 hover:-translate-y-px"
                  style={{ background: 'linear-gradient(180deg,#ecd9a8,#cfa654)', boxShadow: '0 10px 28px -12px rgba(217,184,110,.5)' }}>
                  Get started
                </button>
              </div>
            </div>
          </div>
        </nav>

        <div className="mx-auto max-w-6xl px-5 sm:px-8">
          {/* Hero */}
          <section className="grid lg:grid-cols-[1.05fr_1fr] gap-6 lg:gap-2 items-center pt-10 sm:pt-16 lg:pt-10 pb-6" id="start">
            <div className="text-center lg:text-left">
              <Reveal>
                <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-3.5 py-1.5 text-[13px] font-medium text-[#d6c9a8] backdrop-blur-md">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#d9b86e', boxShadow: '0 0 10px #d9b86e' }} />
                  Your personal AI tutor
                </div>
              </Reveal>

              <Reveal delay={0.08}>
                <h1 className="font-display text-[44px] leading-[1.04] sm:text-6xl lg:text-[72px] font-medium tracking-tight text-[#f2f4f8] mt-7">
                  Learn anything.
                  <br />
                  <em className="italic font-normal"
                    style={{ background: 'linear-gradient(105deg,#ecd9a8,#cfa654 60%,#b98c3f)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>
                    Master it faster.
                  </em>
                </h1>
              </Reveal>

              <Reveal delay={0.16}>
                <p className="mt-6 text-[17px] sm:text-lg leading-relaxed text-[#98a2b8] max-w-[540px] mx-auto lg:mx-0">
                  Adaptive lessons, practice built from your own mistakes, and exam-ready plans —
                  an AI tutor that teaches the way you learn best.
                </p>
              </Reveal>

              <Reveal delay={0.24}>
                <div className="mt-9 flex flex-wrap gap-3.5 justify-center lg:justify-start">
                  <button onClick={() => navigate('/signup')}
                    className="rounded-2xl px-7 py-3.5 text-[15.5px] font-semibold text-[#201a0e] cursor-pointer transition-all duration-150 hover:-translate-y-0.5 active:scale-[0.98]"
                    style={{ background: 'linear-gradient(180deg,#ecd9a8,#cfa654)', boxShadow: '0 16px 44px -14px rgba(217,184,110,.55)' }}>
                    Start learning free
                  </button>
                  <button onClick={() => navigate('/login')}
                    className="rounded-2xl px-7 py-3.5 text-[15.5px] font-semibold text-[#eef1f6] cursor-pointer transition-all duration-150 hover:-translate-y-0.5 active:scale-[0.98] border border-white/12 bg-white/[0.06] backdrop-blur-md hover:bg-white/[0.1]"
                    style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,.09)' }}>
                    Sign in
                  </button>
                </div>
                <p className="mt-4 text-[13px] text-[#5d6979]">No credit card · set up in under a minute</p>
              </Reveal>

              <Reveal delay={0.32}>
                <div className="mt-8 flex flex-wrap gap-2 justify-center lg:justify-start">
                  {['Maths', 'Physics', 'Computer Science', 'Chemistry', 'Biology', 'Statistics'].map((s) => (
                    <span key={s} className="rounded-full border border-white/10 bg-white/[0.04] px-3.5 py-1.5 text-[13px] text-[#b7c0cf] backdrop-blur-sm">
                      {s}
                    </span>
                  ))}
                </div>
              </Reveal>
            </div>

            {/* Signature 3D hero — the Learning Core */}
            <Reveal delay={0.2} y={26}>
              <HeroScene />
            </Reveal>
          </section>

          {/* Features */}
          <section className="pt-20 sm:pt-24 pb-4" id="features">
            <Reveal className="text-center">
              <p className="text-[12.5px] font-semibold tracking-[0.14em] uppercase text-[#8b96a9]">Everything in one place</p>
              <h2 className="font-display text-4xl sm:text-[44px] font-medium tracking-tight text-[#f2f4f8] mt-3">
                A tutor that adapts to you
              </h2>
              <p className="mt-4 text-[16px] text-[#98a2b8] max-w-[540px] mx-auto">
                Not another video library — a study partner that watches how you learn and meets you there.
              </p>
            </Reveal>

            <Stagger className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 mt-14" gap={0.08}>
              {FEATURES.map((f) => {
                const s = GLYPH_STYLE[f.tint];
                return (
                  <Stagger.Item key={f.t}>
                    <div className={`group h-full rounded-3xl border border-white/10 bg-white/[0.045] p-7 backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 ${s.hover}`}
                      style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,.06), 0 24px 56px -34px rgba(0,0,0,.8)' }}>
                      <div className={`w-11 h-11 rounded-xl border flex items-center justify-center text-lg mb-5 ${s.box}`}>
                        {f.glyph}
                      </div>
                      <h3 className="font-display text-[19px] font-semibold tracking-tight text-[#eef1f6]">{f.t}</h3>
                      <p className="mt-2.5 text-[14px] leading-relaxed text-[#8b96a9]">{f.d}</p>
                    </div>
                  </Stagger.Item>
                );
              })}
            </Stagger>
          </section>

          {/* How it works */}
          <section className="pt-20 sm:pt-24 pb-4" id="how">
            <Reveal className="text-center">
              <p className="text-[12.5px] font-semibold tracking-[0.14em] uppercase text-[#8b96a9]">How it works</p>
              <h2 className="font-display text-4xl sm:text-[44px] font-medium tracking-tight text-[#f2f4f8] mt-3">
                Three steps to your first win
              </h2>
            </Reveal>

            <Stagger className="grid md:grid-cols-3 gap-5 mt-14" gap={0.12}>
              {[
                { n: '01', t: 'Tell us your goal', d: 'Pick a subject or an exam date. A quick placement finds your level.' },
                { n: '02', t: 'Learn & practice', d: 'Adaptive lessons, quizzes, and a plan that targets your weak spots.' },
                { n: '03', t: 'Track your mastery', d: 'Watch topics turn gold and stay exam-ready with spaced review.' },
              ].map((s) => (
                <Stagger.Item key={s.n}>
                  <div className="relative rounded-3xl border border-white/10 bg-white/[0.04] p-7 backdrop-blur-xl h-full"
                    style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,.05)' }}>
                    <span className="font-display text-[42px] font-medium leading-none"
                      style={{ background: 'linear-gradient(180deg,#ecd9a8,#8a6d35)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>
                      {s.n}
                    </span>
                    <h3 className="font-display text-[19px] font-semibold tracking-tight text-[#eef1f6] mt-4">{s.t}</h3>
                    <p className="mt-2.5 text-[14px] leading-relaxed text-[#8b96a9]">{s.d}</p>
                  </div>
                </Stagger.Item>
              ))}
            </Stagger>
          </section>

          {/* Final CTA */}
          <section className="pt-20 sm:pt-24 pb-10">
            <Reveal>
              <div className="relative overflow-hidden rounded-[28px] border border-white/10 bg-white/[0.045] px-8 py-14 sm:py-16 text-center backdrop-blur-2xl"
                style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,.08), 0 30px 80px -44px rgba(0,0,0,.85)' }}>
                <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-[480px] h-[300px] rounded-full pointer-events-none"
                  style={{ background: 'radial-gradient(closest-side, rgba(217,184,110,.12), transparent 70%)' }} />
                <h2 className="font-display text-4xl sm:text-[46px] font-medium tracking-tight text-[#f2f4f8] relative">
                  Ready to learn smarter?
                </h2>
                <p className="mt-4 text-[16.5px] text-[#98a2b8] relative">Join and get your personalised study plan today.</p>
                <div className="mt-9 flex flex-wrap gap-3.5 justify-center relative">
                  <button onClick={() => navigate('/signup')}
                    className="rounded-2xl px-7 py-3.5 text-[15.5px] font-semibold text-[#201a0e] cursor-pointer transition-all duration-150 hover:-translate-y-0.5 active:scale-[0.98]"
                    style={{ background: 'linear-gradient(180deg,#ecd9a8,#cfa654)', boxShadow: '0 16px 44px -14px rgba(217,184,110,.55)' }}>
                    Create free account
                  </button>
                  <button onClick={() => navigate('/login')}
                    className="rounded-2xl px-7 py-3.5 text-[15.5px] font-semibold text-[#eef1f6] cursor-pointer transition-all duration-150 hover:-translate-y-0.5 border border-white/12 bg-white/[0.06] hover:bg-white/[0.1]"
                    style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,.09)' }}>
                    Sign in
                  </button>
                </div>
              </div>
            </Reveal>
          </section>

          {/* Footer */}
          <footer className="border-t border-white/[0.07] py-8 mb-6 flex flex-wrap items-center justify-between gap-4">
            <p className="text-[13px] text-[#5d6979]">© {new Date().getFullYear()} AI Tutor</p>
            <div className="flex gap-6 text-[13px] text-[#8b96a9]">
              <button onClick={() => navigate('/login')} className="hover:text-[#eef1f6] transition-colors cursor-pointer">Sign in</button>
              <button onClick={() => navigate('/signup')} className="hover:text-[#eef1f6] transition-colors cursor-pointer">Get started</button>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}