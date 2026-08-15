import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import { Flame, ArrowRight, BookOpen, RefreshCw, Trophy, Sparkles, Shield, Swords, Target, CheckCircle2, MessageCircleQuestion, Zap, TrendingUp, NotebookPen, Upload, Brain, Share2, CalendarDays, Camera, FileText, PenLine } from 'lucide-react';
import { useCelebration } from '../components/CelebrationManager';
import StudyBuddyCard from '../components/StudyBuddyCard';
import Stagger from '../components/motion/Stagger';

const TYPE_STYLES = {
  learn:    { color: 'text-brand-700', bg: 'bg-brand-50', label: 'Learn' },
  review:   { color: 'text-amber-700', bg: 'bg-amber-50', label: 'Review' },
  practice: { color: 'text-teal-700', bg: 'bg-teal-50', label: 'Practice' },
};

const QUEST_DIFF_STYLES = {
  easy:   { color: 'text-green-600', bg: 'bg-green-50' },
  medium: { color: 'text-amber-600', bg: 'bg-amber-50' },
  hard:   { color: 'text-red-600', bg: 'bg-red-50' },
};

function GoalRing({ done, target, size = 56, color = '#b98c3f' }) {
  const pct = Math.min(done / Math.max(target, 1), 1);
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct);
  return (
    <svg width={size} height={size} className="transform -rotate-90">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--bd2)" strokeWidth={6} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color}
        strokeWidth={6} strokeLinecap="round"
        strokeDasharray={circ} strokeDashoffset={offset}
        className="transition-all duration-700" />
    </svg>
  );
}

export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { celebrate } = useCelebration();
  const studentId = user?.username || 'anon';

  const [today, setToday] = useState(null);
  const [gam, setGam] = useState(null);
  const [mastery, setMastery] = useState(null);
  const [quests, setQuests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [claimingQuest, setClaimingQuest] = useState(null);
  const [resume, setResume] = useState(null);
  const [reviewDue, setReviewDue] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [sharing, setSharing] = useState(false);
  const [nextExam, setNextExam] = useState(null);
  const [examReadiness, setExamReadiness] = useState(null);

  // C4: share weekly progress card
  const shareWeek = async () => {
    if (sharing) return;
    setSharing(true);
    try {
      const blob = await api.progressCard();
      const file = new File([blob], 'my_week.pdf', { type: 'application/pdf' });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: 'My learning week', text: 'My progress on AI Tutor this week!' });
      } else {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = 'my_week.pdf'; a.click();
        URL.revokeObjectURL(url);
      }
    } catch { /* user cancelled or error — no-op */ }
    setSharing(false);
  };

  useEffect(() => {
    Promise.allSettled([
      api.getToday(),
      api.myGamification(),
      api.masteryHistory(),
      api.myQuests(),
      api.getResume(),
      api.getReviewDueCount(),
      api.getProgressSnapshot(),
      api.getNextExam(),
    ]).then(([t, g, m, q, r, rd, sn, ne]) => {
      if (t.status === 'fulfilled') setToday(t.value);
      if (g.status === 'fulfilled') setGam(g.value);
      if (m.status === 'fulfilled') setMastery(m.value);
      if (q.status === 'fulfilled') setQuests(q.value?.quests || []);
      if (r.status === 'fulfilled') setResume(r.value);
      if (rd.status === 'fulfilled') setReviewDue(rd.value);
      if (sn.status === 'fulfilled') setSnapshot(sn.value);
      if (ne.status === 'fulfilled' && ne.value?.has_exam) {
        setNextExam(ne.value);
        // Readiness % loads lazily so the countdown shows instantly.
        api.examReadiness(ne.value.subject)
          .then((rr) => setExamReadiness(rr?.readiness ?? null))
          .catch(() => {});
      }
      setLoading(false);
    });
  }, [studentId]);

  const handleClaimQuest = async (quest) => {
    if (claimingQuest || quest.progress < quest.target) return;
    setClaimingQuest(quest.quest_id);
    try {
      await api.completeQuest(quest.quest_id);
      setQuests(prev => prev.map(q =>
        q.quest_id === quest.quest_id ? { ...q, completed: true } : q
      ));
      celebrate([{ event: 'daily_goal_completed' }]);
      api.myGamification().then(g => setGam(g)).catch(() => {});
    } catch {}
    setClaimingQuest(null);
  };

  if (loading) {
    return (
      <div className="max-w-lg mx-auto px-4 py-6 space-y-4">
        <div className="skeleton h-16 w-full" />
        <div className="skeleton h-24 w-full" />
        <div className="skeleton h-28 w-full" />
        <div className="grid grid-cols-3 gap-3">
          <div className="skeleton h-20" /><div className="skeleton h-20" /><div className="skeleton h-20" />
        </div>
      </div>
    );
  }

  // Primary CTA
  const firstTask = today?.tasks?.[0];
  const ctaLabel = firstTask
    ? (firstTask.type === 'review' ? 'Start review' : `Continue: ${firstTask.topic}`)
    : 'Start learning';
  const ctaAction = () => {
    if (firstTask?.type === 'review') navigate('/review');
    else if (firstTask) navigate('/tutor', { state: { topic: firstTask.topic } });
    else navigate('/learn');
  };

  const streak = gam?.streak?.current || 0;
  const streakAlive = gam?.streak?.alive !== false;
  const freezesLeft = gam?.streak?.freezes_remaining ?? 2;
  const level = gam?.level || 1;
  const xp = gam?.xp || 0;
  const xpInLevel = gam?.xp_in_level || 0;
  const xpForNext = gam?.xp_for_next_level || 100;
  const dg = gam?.daily_goal || {};
  const answersDone = dg.answers_done || 0;
  const answersTarget = dg.answers_target || 5;
  const reviewsDone = dg.reviews_done || 0;
  const reviewsTarget = dg.reviews_target || 3;
  const goalDone = answersDone + reviewsDone;
  const goalTarget = answersTarget + reviewsTarget;
  const goalComplete = dg.completed || false;
  const counts = mastery?.counts;
  const displayName = user?.username || 'there';
  const hour = new Date().getHours();
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  return (
    <Stagger className="max-w-lg lg:max-w-2xl mx-auto px-4 lg:px-6 py-5 lg:py-8 space-y-4">
      {/* Greeting */}
      <Stagger.Item className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-2xl flex items-center justify-center text-lg font-bold shadow-soft flex-shrink-0 text-[#201a0e]"
          style={{ background: 'linear-gradient(180deg,#ecd9a8,#cfa654)' }}>
          {displayName[0]?.toUpperCase()}
        </div>
        <div>
          <p className="text-xs text-ink-muted">{greet},</p>
          <h2 className="font-display text-2xl font-medium text-ink leading-tight capitalize">{displayName}</h2>
        </div>
      </Stagger.Item>

      {/* Feature #4: Exam countdown card — nearest upcoming exam */}
      {nextExam && (() => {
        const d = nextExam.days_to_exam;
        const dayLabel = d === 0 ? 'Exam is today!' : d === 1 ? 'Exam tomorrow' : `${d} days to exam`;
        const urgent = d <= 3 || (nextExam.behind_by || 0) > 0;
        const soon = d <= 7;
        const theme = urgent
          ? { ring: 'border-red-200', bg: 'from-red-50/70 to-orange-50/60', icon: 'bg-red-600', bar: 'bg-red-500', text: 'text-red-700' }
          : soon
          ? { ring: 'border-amber-200', bg: 'from-amber-50/70 to-yellow-50/60', icon: 'bg-amber-500', bar: 'bg-amber-500', text: 'text-amber-700' }
          : { ring: 'border-brand-200', bg: 'from-brand-50/70 to-yellow-50/40', icon: 'bg-brand-600', bar: 'bg-brand-500', text: 'text-brand-700' };
        return (
          <Stagger.Item>
          <button
            onClick={() => navigate('/exam-plan')}
            className={`w-full text-left rounded-2xl border ${theme.ring} bg-gradient-to-br ${theme.bg} p-4 shadow-soft hover:shadow-card transition-shadow cursor-pointer`}
          >
            <div className="flex items-center gap-3">
              <div className={`w-11 h-11 rounded-xl ${theme.icon} text-white flex items-center justify-center flex-shrink-0`}>
                <CalendarDays size={22} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-bold text-ink capitalize truncate">{nextExam.subject} exam</p>
                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full flex-shrink-0 ${
                    (nextExam.behind_by || 0) > 0 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                  }`}>
                    {(nextExam.behind_by || 0) > 0 ? `behind by ${nextExam.behind_by}` : 'on track'}
                  </span>
                </div>
                <p className="text-xs text-ink-muted mt-0.5">
                  {dayLabel}{nextExam.today_count > 0 ? ` · ${nextExam.today_count} task${nextExam.today_count > 1 ? 's' : ''} today` : ' · nothing scheduled today'}
                </p>
                {examReadiness != null && (
                  <div className="mt-2">
                    <div className="flex items-center justify-between text-[11px] text-ink-muted mb-1">
                      <span>Readiness</span>
                      <span className="font-semibold">{examReadiness}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-white/70 overflow-hidden">
                      <div className={`h-full ${theme.bar} rounded-full transition-all duration-700`} style={{ width: `${examReadiness}%` }} />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </button>
          </Stagger.Item>
        );
      })()}

      {/* Compact stats bar — streak · level · goal */}
      <Stagger.Item>
      <div className="card-tight flex items-stretch divide-x divide-slate-100">
        <div className="flex-1 flex flex-col items-center justify-center gap-0.5 px-1">
          <Flame size={20} className={streakAlive && streak > 0 ? 'text-accent-500' : 'text-slate-300'} />
          <span className={`text-lg font-extrabold leading-none ${streak > 0 ? 'text-accent-600' : 'text-slate-400'}`}>{streak}</span>
          <span className="text-[10px] text-ink-faint font-medium">day streak</span>
          {freezesLeft > 0 && streak > 0 && (
            <div className="flex gap-0.5" title={`${freezesLeft} freeze${freezesLeft > 1 ? 's' : ''}`}>
              {Array.from({ length: freezesLeft }).map((_, i) => <Shield key={i} size={8} className="text-brand-400" />)}
            </div>
          )}
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-1 px-2">
          <div className="flex items-center gap-1">
            <Trophy size={16} className="text-brand-500" />
            <span className="text-lg font-extrabold text-brand-700 leading-none">Lv {level}</span>
          </div>
          <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bd2)' }}>
            <div className="h-full rounded-full transition-all duration-500"
              style={{ width: `${Math.round(xpInLevel / Math.max(xpForNext, 1) * 100)}%`, background: 'linear-gradient(90deg,#d9b86e,#b98c3f)' }} />
          </div>
          <span className="text-[10px] text-ink-faint font-medium">{xp} XP</span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center px-1">
          <div className="relative">
            <GoalRing done={goalDone} target={goalTarget} color={goalComplete ? '#10b981' : '#b98c3f'} />
            <div className="absolute inset-0 flex items-center justify-center">
              {goalComplete ? <CheckCircle2 size={20} className="text-green-500" />
                : <span className="text-xs font-bold text-ink-soft">{goalDone}/{goalTarget}</span>}
            </div>
          </div>
          <span className="text-[10px] text-ink-faint font-medium mt-0.5">daily goal</span>
        </div>
      </div>
      </Stagger.Item>

      {/* A2: Daily Session — THE hero button */}
      <Stagger.Item>
      <button onClick={() => navigate('/session')}
        className="w-full rounded-2xl p-5 flex items-center justify-between text-left text-white active:scale-[0.98] transition-all duration-200 hover:-translate-y-0.5 relative overflow-hidden cursor-pointer"
        style={{ background: 'linear-gradient(135deg,#16202f 0%,#0f1a26 55%,#12343a 100%)', boxShadow: '0 18px 44px -18px rgba(13,17,27,.6), inset 0 1px 0 rgba(255,255,255,.08)' }}>
        <div className="absolute -right-8 -top-10 w-40 h-40 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(closest-side, rgba(217,184,110,.18), transparent 70%)' }} />
        <div className="absolute -left-10 -bottom-14 w-44 h-44 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(closest-side, rgba(95,217,206,.12), transparent 70%)' }} />
        <div className="flex items-center gap-3 relative">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center backdrop-blur-sm"
            style={{ background: 'linear-gradient(180deg,#ecd9a8,#cfa654)', boxShadow: '0 8px 22px -8px rgba(217,184,110,.55)' }}>
            <Zap size={24} className="text-[#201a0e]" />
          </div>
          <div>
            <p className="font-display text-xl font-medium leading-tight">{ctaLabel}</p>
            <p className="text-sm text-white/60 mt-0.5">Review + continue + practice · ~10 min</p>
          </div>
        </div>
        <ArrowRight size={22} className="relative text-[#ecd9a8]" />
      </button>
      </Stagger.Item>

      {/* Resume (contextual) */}
      {resume?.has_session && resume.elapsed_hours < 48 && (
        <Stagger.Item>
        <button onClick={() => navigate('/tutor', { state: { topic: resume.topic } })}
          className="w-full card-tight card-hover flex items-center gap-3 text-left cursor-pointer">
          <div className="w-11 h-11 bg-brand-50 rounded-xl flex items-center justify-center flex-shrink-0">
            <Sparkles size={20} className="text-brand-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-ink text-sm capitalize">Resume: {resume.topic}</p>
            <p className="text-xs text-ink-muted">
              {resume.elapsed_hours < 1 ? 'Just now' : resume.elapsed_hours < 24 ? `${Math.round(resume.elapsed_hours)}h ago` : 'Yesterday'} · {Math.round(resume.mastery * 100)}% mastery
            </p>
          </div>
          <ArrowRight size={16} className="text-ink-faint" />
        </button>
        </Stagger.Item>
      )}

      {/* Review-due (contextual) */}
      {reviewDue && reviewDue.count > 0 && (
        <Stagger.Item>
        <button onClick={() => navigate('/review')}
          className="w-full bg-amber-50 border border-amber-200 rounded-2xl p-4 flex items-center gap-3 hover:bg-amber-100/70 transition-colors active:scale-[0.98] cursor-pointer">
          <div className="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center flex-shrink-0">
            <RefreshCw size={18} className="text-amber-600" />
          </div>
          <div className="text-left flex-1 min-w-0">
            <p className="font-semibold text-amber-800 text-sm">{reviewDue.count} topic{reviewDue.count > 1 ? 's' : ''} due for review</p>
            <p className="text-xs text-amber-600 truncate">{reviewDue.topics?.slice(0, 3).map(t => t.topic).join(', ')}{reviewDue.count > 3 ? ` +${reviewDue.count - 3}` : ''}</p>
          </div>
          <ArrowRight size={16} className="text-amber-400" />
        </button>
        </Stagger.Item>
      )}

      {/* Ask anything */}
      <Stagger.Item>
      <button onClick={() => navigate('/ask')}
        className="w-full bg-white border-2 border-dashed rounded-2xl p-4 flex items-center gap-3 transition-all group cursor-pointer dark:bg-transparent"
        style={{ borderColor: 'var(--bd)' }}>
        <div className="w-10 h-10 bg-brand-50 group-hover:bg-brand-100 rounded-xl flex items-center justify-center transition-colors flex-shrink-0">
          <MessageCircleQuestion size={20} className="text-brand-500" />
        </div>
        <div className="text-left flex-1">
          <p className="font-semibold text-ink-soft text-sm">Got a question? Ask anything</p>
          <p className="text-xs text-ink-faint">Paste a problem, snap a photo — I'll guide you</p>
        </div>
        <ArrowRight size={16} className="text-ink-faint group-hover:text-brand-500 transition-colors" />
      </button>
      </Stagger.Item>

      {/* Feature #1: Step-by-step solver — write one step, checked live */}
      <Stagger.Item>
      <button onClick={() => navigate('/solver')}
        className="w-full bg-white border border-slate-200 hover:border-brand-300 rounded-2xl px-4 py-3 flex items-center gap-3 transition-colors text-left shadow-soft cursor-pointer dark:bg-transparent"
        style={{ borderColor: 'var(--bd)' }}>
        <span className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 text-[#201a0e]"
          style={{ background: 'linear-gradient(180deg,#ecd9a8,#cfa654)' }}><PenLine size={18} /></span>
        <span className="text-sm text-ink-soft flex-1">Stuck mid-problem? <span className="font-semibold text-ink">Solve step by step — checked live</span></span>
        <ArrowRight size={14} className="text-ink-faint" />
      </button>
      </Stagger.Item>

      {/* D1: Check my solution — photo step-check hero row */}
      <Stagger.Item>
      <button onClick={() => navigate('/solve')}
        className="w-full bg-white border border-slate-200 hover:border-brand-300 rounded-2xl px-4 py-3 flex items-center gap-3 transition-colors text-left shadow-soft cursor-pointer dark:bg-transparent"
        style={{ borderColor: 'var(--bd)' }}>
        <span className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 text-white"
          style={{ background: 'linear-gradient(180deg,#0d9488,#0b7269)' }}><Camera size={18} /></span>
        <span className="text-sm text-ink-soft flex-1">Solved on paper? <span className="font-semibold text-ink">Photo it — I'll find your mistake</span></span>
        <ArrowRight size={14} className="text-ink-faint" />
      </button>
      </Stagger.Item>

      {/* Feature: Study buddy shared streak */}
      <Stagger.Item><StudyBuddyCard /></Stagger.Item>

      {/* Feature tiles — chapters / feynman / exam plan */}
      <Stagger.Item>
      <div className="grid grid-cols-3 gap-2">
        <button onClick={() => navigate('/materials')}
          className="card-tight card-hover flex flex-col items-center gap-1.5 py-4 text-center cursor-pointer">
          <Upload size={20} className="text-teal-600" />
          <span className="font-semibold text-xs text-ink-soft leading-tight">My Chapters</span>
        </button>
        <button onClick={() => navigate('/feynman')}
          className="card-tight card-hover flex flex-col items-center gap-1.5 py-4 text-center cursor-pointer">
          <Brain size={20} className="text-brand-600" />
          <span className="font-semibold text-xs text-ink-soft leading-tight">Explain Back</span>
        </button>
        <button onClick={() => navigate('/exam-plan')}
          className="card-tight card-hover flex flex-col items-center gap-1.5 py-4 text-center cursor-pointer">
          <CalendarDays size={20} className="text-accent-500" />
          <span className="font-semibold text-xs text-ink-soft leading-tight">Exam Plan</span>
        </button>
      </div>
      </Stagger.Item>

      {/* Daily Quests */}
      {quests.length > 0 && (
        <Stagger.Item>
        <div className="card">
          <h3 className="section-title mb-3"><Swords size={16} className="text-brand-600" /> Daily Quests</h3>
          <div className="space-y-2">
            {quests.map(q => {
              const diffStyle = QUEST_DIFF_STYLES[q.difficulty] || QUEST_DIFF_STYLES.medium;
              const pct = Math.min(q.progress / Math.max(q.target, 1), 1);
              const ready = q.progress >= q.target && !q.completed;
              return (
                <div key={q.quest_id}
                  className={`p-3 rounded-xl border transition-all ${q.completed ? 'bg-green-50 border-green-200' : ready ? 'bg-brand-50 border-brand-200' : 'bg-slate-50 border-slate-100'}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className={`font-semibold text-sm ${q.completed ? 'text-green-700 line-through' : 'text-ink'}`}>{q.title}</p>
                        <span className={`pill ${diffStyle.bg} ${diffStyle.color}`}>{q.difficulty}</span>
                      </div>
                      <p className="text-xs text-ink-faint mt-0.5">{q.description}</p>
                      {!q.completed && (
                        <div className="mt-2 flex items-center gap-2">
                          <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bd2)' }}>
                            <div className="h-full bg-brand-500 rounded-full transition-all duration-500" style={{ width: `${Math.round(pct * 100)}%` }} />
                          </div>
                          <span className="text-[10px] font-medium text-ink-muted">{q.progress}/{q.target}</span>
                        </div>
                      )}
                    </div>
                    <div className="flex-shrink-0 flex items-center gap-1.5">
                      <span className="text-xs font-bold text-brand-600">+{q.xp_reward} XP</span>
                      {q.completed ? <CheckCircle2 size={20} className="text-green-500" />
                        : ready ? (
                          <button onClick={() => handleClaimQuest(q)} disabled={claimingQuest === q.quest_id}
                            className="px-2.5 py-1 bg-brand-600 text-white text-xs font-bold rounded-lg hover:bg-brand-700 transition-colors disabled:opacity-50 cursor-pointer">Claim</button>
                        ) : <Target size={16} className="text-slate-300" />}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        </Stagger.Item>
      )}

      {/* Today's Plan */}
      {today?.tasks?.length > 0 && (
        <Stagger.Item>
        <div className="card">
          <h3 className="section-title mb-3">Today's Plan</h3>
          <div className="space-y-2">
            {today.tasks.map((task, i) => {
              const style = TYPE_STYLES[task.type] || TYPE_STYLES.learn;
              return (
                <button key={i}
                  onClick={() => { if (task.type === 'review') navigate('/review'); else navigate('/tutor', { state: { topic: task.topic } }); }}
                  className="w-full flex items-center justify-between p-3 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors text-left cursor-pointer">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className={`pill ${style.bg} ${style.color} flex-shrink-0`}>{style.label}</span>
                    <div className="min-w-0">
                      <p className="font-semibold text-ink capitalize text-sm truncate">{task.topic}</p>
                      <p className="text-xs text-ink-faint truncate">{task.reason}</p>
                    </div>
                  </div>
                  <ArrowRight size={16} className="text-ink-faint flex-shrink-0" />
                </button>
              );
            })}
          </div>
        </div>
        </Stagger.Item>
      )}

      {/* This Week snapshot + share */}
      {snapshot && snapshot.topics_touched_this_week > 0 && (
        <Stagger.Item>
        <div className="bg-gradient-to-br from-emerald-50/80 to-teal-50/60 border border-emerald-200 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="section-title text-emerald-900"><TrendingUp size={16} className="text-emerald-600" /> This Week</h3>
            <button onClick={shareWeek} disabled={sharing}
              className="text-xs px-2.5 py-1 rounded-lg bg-white border border-emerald-200 text-emerald-700 hover:bg-emerald-50 transition-colors flex items-center gap-1 disabled:opacity-50 cursor-pointer">
              <Share2 size={12} /> {sharing ? '…' : 'Share'}
            </button>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center mb-3">
            <div><p className="text-xl font-extrabold text-emerald-700">{snapshot.topics_touched_this_week}</p><p className="text-[10px] text-ink-muted">Topics</p></div>
            <div><p className="text-xl font-extrabold text-emerald-700">{snapshot.questions_this_week}</p><p className="text-[10px] text-ink-muted">Questions</p></div>
            <div><p className="text-xl font-extrabold text-emerald-700">+{Math.round(snapshot.total_mastery_gain * 100)}%</p><p className="text-[10px] text-ink-muted">Growth</p></div>
          </div>
          {snapshot.topics_list?.length > 0 && (
            <div className="space-y-1.5">
              {snapshot.topics_list.slice(0, 3).map((t, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="flex-1 text-ink-soft capitalize truncate">{t.topic}</span>
                  <span className="text-emerald-600 font-semibold">+{Math.round(t.gain * 100)}%</span>
                  <div className="w-16 h-1.5 rounded-full bg-emerald-100 overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.round(t.mastery_now * 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
          {snapshot.next_up && <p className="text-xs text-emerald-700 mt-2 font-medium">Next up: <span className="capitalize">{snapshot.next_up}</span></p>}
          {snapshot.message && <p className="text-[10px] text-ink-faint mt-1.5 italic">{snapshot.message}</p>}
        </div>
        </Stagger.Item>
      )}

      {/* Mastery */}
      {counts && counts.total > 0 && (
        <Stagger.Item>
        <div className="card">
          <h3 className="section-title mb-3">Your mastery</h3>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div><p className="text-xl font-extrabold text-green-600">{counts.mastered}</p><p className="text-xs text-ink-faint">Mastered</p></div>
            <div><p className="text-xl font-extrabold text-amber-500">{counts.in_progress}</p><p className="text-xs text-ink-faint">Learning</p></div>
            <div><p className="text-xl font-extrabold text-slate-300">{counts.not_started}</p><p className="text-xs text-ink-faint">Not started</p></div>
          </div>
          <div className="flex h-2 rounded-full overflow-hidden mt-3" style={{ background: 'var(--bd2)' }}>
            {counts.mastered > 0 && <div className="bg-green-500" style={{ width: `${Math.round(counts.mastered / counts.total * 100)}%` }} />}
            {counts.in_progress > 0 && <div className="bg-amber-400" style={{ width: `${Math.round(counts.in_progress / counts.total * 100)}%` }} />}
          </div>
        </div>
        </Stagger.Item>
      )}

      {/* Badges */}
      {gam?.badges?.length > 0 && (
        <Stagger.Item>
        <div className="card">
          <h3 className="section-title mb-3">Badges</h3>
          <div className="flex flex-wrap gap-2">
            {gam.badges.map(b => (
              <div key={b.id} className="flex items-center gap-1.5 bg-slate-50 rounded-xl px-3 py-1.5" title={b.description}>
                <span className="text-lg">{b.emoji}</span>
                <span className="text-xs font-medium text-ink-soft">{b.name}</span>
              </div>
            ))}
          </div>
        </div>
        </Stagger.Item>
      )}

      {/* Quick actions */}
      <Stagger.Item>
      <div>
        <h3 className="section-title mb-2 px-1 text-ink-muted">More</h3>
        <div className="grid grid-cols-3 gap-2">
          {[
            { to: '/learn', icon: BookOpen, color: 'text-brand-500', label: 'Topics' },
            { to: '/review', icon: RefreshCw, color: 'text-amber-500', label: 'Review' },
            { to: '/mistakes', icon: Zap, color: 'text-red-500', label: 'Mistakes' },
            { to: '/notebook', icon: NotebookPen, color: 'text-teal-500', label: 'Notebook' },
            { to: '/flashcards', icon: Sparkles, color: 'text-brand-500', label: 'Cards' },
          { to: '/cheatsheet', icon: FileText, color: 'text-indigo-500', label: 'Cheat sheet' },
          ].map(({ to, icon: Icon, color, label }) => (
            <button key={to} onClick={() => navigate(to)}
              className="card-tight card-hover flex flex-col items-center gap-1.5 py-3 cursor-pointer">
              <Icon size={20} className={color} />
              <span className="font-medium text-[11px] text-ink-soft">{label}</span>
            </button>
          ))}
        </div>
      </div>
      </Stagger.Item>
    </Stagger>
  );
}