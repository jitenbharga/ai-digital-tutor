import { useNavigate } from 'react-router-dom';
import Logo from '../components/Logo';

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&display=swap');
.lp{--bg:#07080c;--ink:#f4f5f9;--mut:#98a0b4;--mut2:#6b7285;--line:rgba(255,255,255,.10);
  --b1:#818cf8;--b2:#a78bfa;
  --glass:rgba(255,255,255,.055);--glass-str:rgba(255,255,255,.09);--glass-brd:rgba(255,255,255,.12);
  font-family:'Inter',system-ui,sans-serif;color:var(--ink);background:var(--bg);min-height:100vh;overflow-x:hidden}
.lp *{box-sizing:border-box;margin:0;padding:0}
.lp a{color:inherit;text-decoration:none}
/* Override the app's global dark h1-h4 color for the dark landing */
.lp h1,.lp h2,.lp h3,.lp h4{color:var(--ink)}
.lp-bg{position:fixed;inset:0;z-index:0;pointer-events:none;
  background:
   radial-gradient(1000px 640px at 50% -16%, rgba(129,140,248,.30), transparent 60%),
   radial-gradient(780px 560px at 86% 6%, rgba(167,139,250,.20), transparent 58%),
   radial-gradient(760px 640px at 6% 34%, rgba(56,189,248,.12), transparent 60%),
   radial-gradient(700px 560px at 92% 88%, rgba(129,140,248,.12), transparent 60%),
   linear-gradient(180deg,#080a12,#06070c 70%)}
.lp-wrap{position:relative;z-index:1;max-width:1080px;margin:0 auto;padding:0 28px}

/* Glass sticky nav */
.lp-nav{position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;
  padding:16px 22px;margin:14px auto 0;max-width:1040px;border-radius:18px;
  background:var(--glass);border:1px solid var(--glass-brd);
  backdrop-filter:blur(20px) saturate(150%);-webkit-backdrop-filter:blur(20px) saturate(150%);
  box-shadow:0 10px 40px -18px rgba(0,0,0,.6), inset 0 1px 0 rgba(255,255,255,.08)}
.lp-logo{display:flex;align-items:center;gap:11px;font-weight:700;font-size:19px;letter-spacing:-.01em}
.lp-logo .m{width:32px;height:32px;border-radius:9px;display:grid;place-items:center;color:#fff;font-size:17px;
  background:linear-gradient(135deg,var(--b1),var(--b2))}
.lp-navlinks{display:flex;align-items:center;gap:30px}
.lp-navlinks a{color:var(--mut);font-size:14.5px;font-weight:450;transition:color .18s}
.lp-navlinks a:hover{color:var(--ink)}
.lp-nav-cta{display:flex;align-items:center;gap:14px}
.lp-ghost{color:var(--mut);font-weight:500;font-size:14.5px;padding:8px 4px;transition:color .18s;cursor:pointer;background:none;border:0;font-family:inherit}
.lp-ghost:hover{color:var(--ink)}
/* Glass buttons */
.lp-btn{cursor:pointer;font-family:inherit;font-weight:600;font-size:14.5px;padding:11px 20px;border-radius:12px;
  color:var(--ink);background:var(--glass-str);border:1px solid var(--glass-brd);
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
  transition:transform .14s,background .2s,border-color .2s,box-shadow .25s;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.12)}
.lp-btn:hover{transform:translateY(-1px);background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.22)}
.lp-btn.big{font-size:15.5px;padding:15px 30px;border-radius:14px}
/* Primary = brighter frosted with brand tint */
.lp-btn.primary{color:#0b0c12;background:linear-gradient(180deg,rgba(255,255,255,.96),rgba(255,255,255,.82));border-color:rgba(255,255,255,.5)}
.lp-btn.primary:hover{background:#fff;box-shadow:0 16px 44px -16px rgba(199,205,247,.5)}

.lp-hero{text-align:center;padding:104px 0 60px}
.lp-badge{display:inline-flex;align-items:center;gap:9px;font-size:13px;font-weight:500;color:#d6dafb;
  background:var(--glass);border:1px solid var(--glass-brd);padding:7px 16px;border-radius:999px;margin-bottom:38px;
  backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);box-shadow:inset 0 1px 0 rgba(255,255,255,.1)}
.lp-badge .dot{width:6px;height:6px;border-radius:50%;background:#a78bfa;box-shadow:0 0 12px #a78bfa}
.lp-h1{font-family:'Instrument Serif',Georgia,serif;font-weight:400;font-size:clamp(48px,8.4vw,90px);line-height:1.02;letter-spacing:-.005em}
.lp-h1 em{font-style:italic;background:linear-gradient(110deg,#c7d2fe,#a78bfa 55%,#818cf8);-webkit-background-clip:text;background-clip:text;color:transparent}
.lp-sub{max-width:600px;margin:30px auto 0;font-size:clamp(16px,1.8vw,19px);line-height:1.65;color:var(--mut);font-weight:400}
.lp-cta{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin-top:42px}
.lp-note{margin-top:20px;font-size:13px;color:var(--mut2)}
.lp-strip{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin:56px 0 0}
.lp-chip{font-size:13px;font-weight:450;color:#c3c9db;background:var(--glass);border:1px solid var(--glass-brd);padding:8px 15px;border-radius:999px;
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}

.lp-sec{padding:100px 0 0;text-align:center}
.lp-eyebrow{font-size:12.5px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:#98a0b4}
.lp-h2{font-family:'Instrument Serif',Georgia,serif;font-weight:400;font-size:clamp(32px,4.4vw,50px);letter-spacing:-.005em;margin-top:14px}
.lp-h2-sub{max-width:540px;margin:18px auto 0;color:var(--mut);font-size:16px;line-height:1.65}
.lp-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:56px;text-align:left}
/* Frosted glass cards */
.lp-card{background:var(--glass);border:1px solid var(--glass-brd);border-radius:20px;padding:26px;
  backdrop-filter:blur(20px) saturate(140%);-webkit-backdrop-filter:blur(20px) saturate(140%);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.08), 0 20px 50px -30px rgba(0,0,0,.7);
  transition:transform .25s,border-color .25s,background .25s}
.lp-card:hover{transform:translateY(-4px);border-color:rgba(129,140,248,.4);background:var(--glass-str)}
.lp-card .ic{width:40px;height:40px;border-radius:11px;display:grid;place-items:center;font-size:19px;margin-bottom:18px;
  color:#d6dafb;background:rgba(255,255,255,.08);border:1px solid var(--glass-brd)}
.lp-card h3{font-size:16.5px;font-weight:600;letter-spacing:-.01em}
.lp-card p{margin-top:9px;font-size:14px;line-height:1.65;color:var(--mut)}

.lp-final{margin:112px 0 92px;padding:66px 32px;text-align:center;border-radius:28px;position:relative;overflow:hidden;
  background:var(--glass);border:1px solid var(--glass-brd);
  backdrop-filter:blur(26px) saturate(150%);-webkit-backdrop-filter:blur(26px) saturate(150%);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.1), 0 30px 80px -40px rgba(0,0,0,.8)}
.lp-final h2{font-family:'Instrument Serif',Georgia,serif;font-weight:400;font-size:clamp(30px,4vw,46px);letter-spacing:-.005em}
.lp-final p{margin-top:14px;color:var(--mut);font-size:16.5px}
.lp-final .lp-cta{margin-top:34px}

.lp-foot{border-top:1px solid var(--line);padding:32px 0 56px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px}
.lp-foot .c{color:var(--mut2);font-size:13px}
.lp-foot .lks{display:flex;gap:24px}.lp-foot .lks a{color:var(--mut);font-size:13px;cursor:pointer}.lp-foot .lks a:hover{color:var(--ink)}

@media(max-width:760px){
  .lp-navlinks{display:none}
  .lp-cards{grid-template-columns:1fr}
  .lp-hero{padding:64px 0 32px}
  .lp-sec{padding:76px 0 0}
}
`;

const FEATURES = [
  { ic: '◎', t: 'Adaptive AI tutoring', d: 'Lessons that read your level and move between direct teaching and Socratic questioning as you go.' },
  { ic: '◈', t: 'Practice your weak spots', d: 'One tap builds a targeted set from the exact questions and concepts you keep getting wrong.' },
  { ic: '◱', t: 'Exam-ready plans', d: 'A day-by-day plan to your exam date with a live readiness meter, so you always know where you stand.' },
  { ic: '❖', t: 'Learn by explaining', d: 'Explain a topic back in your own words and get graded — the fastest way to make it stick.' },
  { ic: '✎', t: 'Step-by-step solver', d: 'Write your working by hand; the tutor checks each step and nudges you the moment you slip.' },
  { ic: '▤', t: 'Flashcards, offline', d: 'Cards build themselves from your mistakes and sync your reviews even without a connection.' },
];

export default function Landing() {
  const navigate = useNavigate();
  return (
    <div className="lp">
      <style>{CSS}</style>
      <div className="lp-bg" />

      <nav className="lp-nav">
        <div className="lp-logo"><Logo size={32} /> AI Tutor</div>
        <div className="lp-navlinks">
          <a href="#features">Features</a>
          <a href="#how">How it works</a>
          <a href="#start">Get started</a>
        </div>
        <div className="lp-nav-cta">
          <button className="lp-ghost" onClick={() => navigate('/login')}>Sign in</button>
          <button className="lp-btn primary" onClick={() => navigate('/signup')}>Get started</button>
        </div>
      </nav>

      <div className="lp-wrap">
        <section className="lp-hero">
          <div className="lp-badge"><span className="dot" /> Your personal AI tutor</div>
          <h1 className="lp-h1">Learn anything.<br /><em>Master it faster.</em></h1>
          <p className="lp-sub">
            Adaptive lessons, practice built from your own mistakes, and exam-ready plans —
            an AI tutor that teaches the way you learn best.
          </p>
          <div className="lp-cta" id="start">
            <button className="lp-btn big primary" onClick={() => navigate('/signup')}>Start learning free</button>
            <button className="lp-btn big" onClick={() => navigate('/login')}>Sign in</button>
          </div>
          <p className="lp-note">No credit card · set up in under a minute</p>

          <div className="lp-strip">
            <span className="lp-chip">Maths</span>
            <span className="lp-chip">Physics</span>
            <span className="lp-chip">Computer Science</span>
            <span className="lp-chip">Chemistry</span>
            <span className="lp-chip">Biology</span>
            <span className="lp-chip">Statistics</span>
          </div>
        </section>

        <section className="lp-sec" id="features">
          <div className="lp-eyebrow">Everything in one place</div>
          <h2 className="lp-h2">A tutor that adapts to you</h2>
          <p className="lp-h2-sub">Not another video library — a study partner that watches how you learn and meets you there.</p>
          <div className="lp-cards">
            {FEATURES.map((f, i) => (
              <div className="lp-card" key={i}>
                <div className="ic">{f.ic}</div>
                <h3>{f.t}</h3>
                <p>{f.d}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="lp-sec" id="how">
          <div className="lp-eyebrow">How it works</div>
          <h2 className="lp-h2">Three steps to your first win</h2>
          <div className="lp-cards">
            <div className="lp-card"><div className="ic">1</div><h3>Tell us your goal</h3><p>Pick a subject or an exam date. A quick placement finds your level.</p></div>
            <div className="lp-card"><div className="ic">2</div><h3>Learn &amp; practice</h3><p>Adaptive lessons, quizzes, and a plan that targets your weak spots.</p></div>
            <div className="lp-card"><div className="ic">3</div><h3>Track your mastery</h3><p>Watch topics turn green and stay exam-ready with spaced review.</p></div>
          </div>
        </section>

        <section className="lp-final">
          <h2>Ready to learn smarter?</h2>
          <p>Join and get your personalised study plan today.</p>
          <div className="lp-cta">
            <button className="lp-btn big primary" onClick={() => navigate('/signup')}>Create free account</button>
            <button className="lp-btn big" onClick={() => navigate('/login')}>Sign in</button>
          </div>
        </section>

        <footer className="lp-foot">
          <div className="c">© {new Date().getFullYear()} AI Tutor</div>
          <div className="lks">
            <a onClick={() => navigate('/login')}>Sign in</a>
            <a onClick={() => navigate('/signup')}>Get started</a>
          </div>
        </footer>
      </div>
    </div>
  );
}
