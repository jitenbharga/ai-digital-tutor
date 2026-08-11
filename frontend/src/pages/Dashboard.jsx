import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { api, getToken } from '../lib/api';
import KnowledgeGraphViz from '../components/KnowledgeGraph3D';
import CertificateModal from '../components/CertificateModal';
import {
  TrendingUp, Target, Clock, BookOpen, CheckCircle, Flame, Award,
  Download, RefreshCw, Sparkles, ArrowUp, Zap,
} from 'lucide-react';
// W6: presentational sub-components extracted to their own files + Vitest-tested.
import StatCard from '../components/dashboard/StatCard';
import MasteryCounts from '../components/dashboard/MasteryCounts';
import TrendBadge from '../components/dashboard/TrendBadge';

/* ─── Mini Sparkline (SVG) ─── */
function Sparkline({ snapshots, width = 120, height = 32 }) {
  if (!snapshots || snapshots.length < 2) {
    return <div className="text-xs text-gray-400 italic" style={{ width }}>Not enough data</div>;
  }

  const values = snapshots.map(s => s.mastery);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 0.1;

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - 4 - ((v - min) / range) * (height - 8);
    return `${x},${y}`;
  }).join(' ');

  // Color based on trend direction
  const trending = values[values.length - 1] >= values[0];
  const color = trending ? '#22c55e' : '#f59e0b';

  return (
    <svg width={width} height={height} className="block">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* End dot */}
      <circle
        cx={(values.length - 1) / (values.length - 1) * width}
        cy={height - 4 - ((values[values.length - 1] - min) / range) * (height - 8)}
        r="3"
        fill={color}
      />
    </svg>
  );
}

/* ─── Mastery History Table with Sparklines ─── */
function MasteryHistory({ history }) {
  if (!history?.length) return null;
  const sorted = [...history].sort((a, b) => b.current_mastery - a.current_mastery);

  return (
    <div className="card">
      <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <TrendingUp size={18} className="text-brand-500" /> Mastery Over Time
      </h3>
      <div className="space-y-2">
        {sorted.map((topic) => {
          const m = topic.current_mastery;
          const barColor = m >= 0.8 ? 'bg-green-500' : m >= 0.4 ? 'bg-amber-500' : 'bg-red-400';
          const textColor = m >= 0.8 ? 'text-green-600' : m >= 0.4 ? 'text-amber-600' : 'text-red-500';

          return (
            <div key={topic.topic} className="flex items-center gap-3 py-1.5">
              <span className="text-sm font-medium w-32 truncate text-gray-700">{topic.topic}</span>
              <div className="flex-1 bg-gray-100 rounded-full h-2.5 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                  style={{ width: `${Math.max(3, m * 100)}%` }}
                />
              </div>
              <span className={`text-xs font-semibold w-10 text-right ${textColor}`}>
                {Math.round(m * 100)}%
              </span>
              <Sparkline snapshots={topic.snapshots} width={100} height={28} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Review Panel ─── */
function ReviewPanel({ data }) {
  if (!data) return null;
  return (
    <div className="card">
      <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <Clock size={18} /> Due for Review
      </h3>
      <p className="text-sm text-gray-600 mb-3">{data.message}</p>
      {data.due_topics?.length > 0 && (
        <div className="space-y-2">
          {data.due_topics.map((t, i) => (
            <div key={i} className="flex items-center justify-between text-sm bg-gray-50 px-3 py-2 rounded-lg">
              <span className="font-medium">{t.topic}</span>
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <span>Mastery: {(t.mastery * 100).toFixed(0)}%</span>
                <span>Retention: {(t.retention_estimate * 100).toFixed(0)}%</span>
                <span>{t.days_since_review.toFixed(1)}d ago</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Study Plan Panel ─── */
function StudyPlanPanel({ data }) {
  if (!data?.plan?.length) return null;
  return (
    <div className="card">
      <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <BookOpen size={18} /> Study Plan
      </h3>
      <div className="space-y-2">
        {data.plan.map((item, i) => (
          <div key={i} className="flex items-center gap-3 text-sm bg-gray-50 px-3 py-2 rounded-lg">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
              item.type === 'review' ? 'bg-blue-100 text-blue-700' :
              item.type === 'learn' ? 'bg-green-100 text-green-700' :
              'bg-purple-100 text-purple-700'
            }`}>{item.type}</span>
            <span className="font-medium flex-1">{item.topic}</span>
            <span className="text-gray-500">{item.duration_min} min</span>
          </div>
        ))}
      </div>
      {data.motivational_note && (
        <p className="mt-3 text-sm text-green-700 bg-green-50 p-3 rounded-lg">{data.motivational_note}</p>
      )}
    </div>
  );
}

/* ─── Gamification Panel ─── */
function GamificationPanel({ data }) {
  if (!data) return null;
  const pct = data.xp_in_level && data.xp_for_next_level
    ? Math.min(100, (data.xp_in_level / data.xp_for_next_level) * 100)
    : 0;
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          <Award size={18} /> Level {data.level}
        </h3>
        <div className="flex items-center gap-2 text-sm">
          <Flame size={16} className="text-orange-500" />
          <span className="font-bold text-orange-600">{data.current_streak} day streak</span>
        </div>
      </div>
      <div className="mb-1 flex justify-between text-xs text-gray-500">
        <span>{data.xp} XP total</span>
        <span>{data.xp_in_level} / {data.xp_for_next_level} to next level</span>
      </div>
      <div className="bg-gray-100 rounded-full h-4 overflow-hidden mb-4">
        <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-purple-500 transition-all duration-700"
          style={{ width: `${pct}%` }} />
      </div>
      {data.badges?.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 mb-2">Badges earned</p>
          <div className="flex flex-wrap gap-2">
            {data.badges.map((b, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-full text-xs font-medium text-amber-800"
                title={b.description}>
                {b.emoji} {b.name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════ MAIN DASHBOARD ═══════════════ */

export default function Dashboard() {
  const { user } = useAuth();
  const studentId = user?.username || 'anon';
  const [progress, setProgress] = useState(null);
  const [graph, setGraph] = useState(null);
  const [reviewData, setReviewData] = useState(null);
  const [planData, setPlanData] = useState(null);
  const [gamification, setGamification] = useState(null);
  const [masteryData, setMasteryData] = useState(null);
  const [pathData, setPathData] = useState(null);
  const [certsData, setCertsData] = useState(null);
  const [selectedCert, setSelectedCert] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const graphContainerRef = useRef(null);
  const [graphWidth, setGraphWidth] = useState(500);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    const results = await Promise.allSettled([
      api.progress(studentId),
      api.knowledgeGraph(studentId),
      api.review(studentId),
      api.studyPlan(studentId),
      api.gamification(studentId),
      api.masteryHistory(),
      api.getPath(),
      api.getCertificates(),
    ]);

    if (results[0].status === 'fulfilled') setProgress(results[0].value);
    if (results[1].status === 'fulfilled') setGraph(results[1].value);
    if (results[2].status === 'fulfilled') setReviewData(results[2].value);
    if (results[3].status === 'fulfilled') setPlanData(results[3].value);
    if (results[4].status === 'fulfilled') setGamification(results[4].value);
    if (results[5].status === 'fulfilled') setMasteryData(results[5].value);
    if (results[6].status === 'fulfilled') setPathData(results[6].value);
    if (results[7].status === 'fulfilled') setCertsData(results[7].value);

    setLoading(false);
    setRefreshing(false);
  }, [studentId]);

  useEffect(() => { loadData(); }, [loadData]);

  // Responsive graph width
  useEffect(() => {
    if (!graphContainerRef.current) return;
    const ro = new ResizeObserver(entries => {
      for (const e of entries) setGraphWidth(e.contentRect.width);
    });
    ro.observe(graphContainerRef.current);
    return () => ro.disconnect();
  }, []);

  const handleDownloadReport = async () => {
    try {
      const token = getToken();
      const res = await fetch('/api/me/report', {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Report generation failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `progress_report_${studentId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-brand-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  const hasData = progress?.total_questions > 0;

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      {/* Header with Reload + Download */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-bold text-gray-900">Your Mastery Dashboard</h2>
          {masteryData?.overall_trend && <TrendBadge trend={masteryData.overall_trend} />}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => loadData(true)}
            disabled={refreshing}
            className="btn-secondary text-sm flex items-center gap-2"
          >
            <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
            {refreshing ? 'Refreshing...' : 'Reload'}
          </button>
          <button onClick={handleDownloadReport} className="btn-secondary text-sm flex items-center gap-2">
            <Download size={16} /> Report
          </button>
        </div>
      </div>

      {!hasData && (
        <div className="card text-center py-12">
          <Zap size={48} className="mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-semibold text-gray-700 mb-2">Your journey starts here</h3>
          <p className="text-gray-500">Answer some questions to see your mastery grow!</p>
        </div>
      )}

      {hasData && (
        <>
          {/* Gamification + Mastery Counts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GamificationPanel data={gamification} />
            <MasteryCounts counts={masteryData?.counts} />
          </div>

          {/* Stats cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard icon={CheckCircle} label="Total Questions" value={progress?.total_questions || 0} />
            <StatCard icon={TrendingUp} label="Accuracy" value={`${progress?.accuracy || 0}%`} color="text-green-600" bg="bg-green-50" />
            <StatCard icon={Target} label="Topics Studied" value={Object.keys(progress?.topics || {}).length} color="text-purple-600" bg="bg-purple-50" />
          </div>

          {/* Interactive Skill Map + Mastery Legend */}
          <div className="card" ref={graphContainerRef}>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Sparkles size={18} className="text-brand-500" /> Interactive Skill Map
            </h3>
            <p className="text-xs text-gray-500 mb-2">
              Node size and color reflect your mastery. Edges show prerequisite relationships. Drag to explore.
            </p>
            <div className="border border-gray-100 rounded-lg overflow-hidden bg-white">
              <KnowledgeGraphViz data={graph} width={graphWidth - 48} height={400} />
            </div>
            <div className="flex flex-wrap gap-4 mt-3 text-xs text-gray-500">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-green-500 inline-block" /> Mastered (&gt;80%)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-blue-500 inline-block" /> In Progress (40-80%)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-red-400 inline-block" /> Weak (&lt;40%)</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-amber-500 inline-block" /> Suggested Focus</span>
            </div>
            {graph?.suggested_focus && (
              <p className="mt-3 text-sm text-brand-600 bg-brand-50 p-3 rounded-lg">
                <Target size={14} className="inline mr-1 -mt-0.5" />
                {graph.suggested_focus}
              </p>
            )}
          </div>

          {/* Mastery-over-time sparklines */}
          <MasteryHistory history={masteryData?.history} />

          {/* Learning Path progress (if set) */}
          {pathData?.goal && pathData.path?.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <BookOpen size={18} /> Learning Path: {pathData.goal}
              </h3>
              <div className="flex items-center gap-4 mb-2">
                <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-brand-500 to-green-500 h-full rounded-full transition-all duration-700"
                    style={{ width: `${pathData.progress_pct}%` }}
                  />
                </div>
                <span className="text-sm font-semibold text-brand-600">{pathData.progress_pct}%</span>
              </div>
              {pathData.current_topic && (
                <p className="text-sm text-gray-600">
                  Currently working on: <span className="font-medium text-gray-900 capitalize">{pathData.current_topic}</span>
                </p>
              )}
            </div>
          )}

          {/* Certificates */}
          {certsData?.certificates?.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Award size={18} className="text-amber-500" /> Certificates Earned ({certsData.total})
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {certsData.certificates.map((cert) => {
                  const colors = {
                    Proficiency: 'border-blue-200 bg-blue-50',
                    Excellence: 'border-purple-200 bg-purple-50',
                    Mastery: 'border-amber-200 bg-amber-50',
                  };
                  const textColors = {
                    Proficiency: 'text-blue-700',
                    Excellence: 'text-purple-700',
                    Mastery: 'text-amber-700',
                  };
                  return (
                    <button
                      key={cert.cert_id}
                      onClick={() => setSelectedCert(cert)}
                      className={`p-3 rounded-lg border-2 text-left hover:shadow-md transition-shadow ${colors[cert.tier] || colors.Proficiency}`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-xs font-bold uppercase ${textColors[cert.tier] || textColors.Proficiency}`}>
                          {cert.tier}
                        </span>
                        <span className="text-xs text-gray-400">{cert.awarded_at?.slice(0, 10)}</span>
                      </div>
                      <p className="font-medium text-gray-900 capitalize">{cert.topic}</p>
                      <p className="text-xs text-gray-500">{Math.round(cert.mastery * 100)}% mastery</p>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Review + Study Plan */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ReviewPanel data={reviewData} />
            <StudyPlanPanel data={planData} />
          </div>
        </>
      )}

      {/* Certificate detail modal */}
      {selectedCert && (
        <CertificateModal certificate={selectedCert} onClose={() => setSelectedCert(null)} />
      )}
    </div>
  );
}
