import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { ArrowLeft, Play, SkipForward, ChevronDown, ChevronRight, Clock, CheckCircle2, Circle, Lock, AlertTriangle, Rocket, ExternalLink, Video, FileText, GraduationCap, GitBranch, ScrollText } from 'lucide-react';
import ProjectBrief from '../components/ProjectBrief';

const STATUS_STYLES = {
  done:        { bg: 'bg-green-100', border: 'border-green-300', text: 'text-green-800', icon: CheckCircle2, iconColor: 'text-green-500' },
  in_progress: { bg: 'bg-blue-50',  border: 'border-blue-300',  text: 'text-blue-800',  icon: Play,         iconColor: 'text-blue-500' },
  not_started: { bg: 'bg-gray-50',  border: 'border-gray-200',  text: 'text-gray-600',  icon: Circle,       iconColor: 'text-gray-400' },
  skipped:     { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700',  icon: SkipForward,  iconColor: 'text-amber-500' },
};

function ProgressHeader({ stats, subjectTitle }) {
  const pct = stats?.progress_pct || 0;
  const hrs = Math.floor((stats?.est_minutes_left || 0) / 60);
  const mins = (stats?.est_minutes_left || 0) % 60;

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-gray-900">{subjectTitle}</h2>
        <div className="flex items-center gap-1.5 text-sm text-gray-500">
          <Clock size={14} />
          <span>{hrs > 0 ? `${hrs}h ${mins}m` : `${mins}m`} left</span>
        </div>
      </div>

      <div className="space-y-1.5">
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">{stats?.done || 0} of {stats?.total || 0} completed</span>
          <span className="font-semibold text-brand-600">{pct}%</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2.5">
          <div
            className="bg-brand-500 h-2.5 rounded-full transition-all duration-700 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="flex gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> {stats?.done || 0} Done</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" /> {stats?.in_progress || 0} Active</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-gray-300" /> {stats?.not_started || 0} Remaining</span>
      </div>
    </div>
  );
}

const RESOURCE_ICONS = { video: Video, paper: GraduationCap, article: FileText };

function ResourceLinks({ subject, nodeId }) {
  const [resources, setResources] = useState(null);
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = () => {
    if (resources) { setShow(!show); return; }
    setLoading(true);
    setError('');
    api.getNodeResources(subject, nodeId)
      .then(res => { setResources(res?.resources || []); setShow(true); })
      .catch(err => { setError(err?.message || 'Could not load resources'); setResources([]); setShow(true); })
      .finally(() => setLoading(false));
  };

  return (
    <div className="mt-1">
      <button onClick={load} disabled={loading}
        className="text-[10px] text-teal-600 hover:text-teal-700 font-medium flex items-center gap-1 disabled:opacity-50">
        <ExternalLink size={10} /> {loading ? 'Loading…' : (show ? 'Hide resources' : 'Learn more')}
      </button>
      {show && !loading && (
        <div className="mt-1 space-y-1">
          {error && <p className="text-[10px] text-red-500">{error}</p>}
          {!error && resources && resources.length === 0 && (
            <p className="text-[10px] text-gray-400">No references found for this topic yet.</p>
          )}
          {resources && resources.map((r, i) => {
            const RIcon = RESOURCE_ICONS[r.type] || FileText;
            return (
              <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-[11px] font-medium text-gray-800 hover:text-brand-600 transition-colors"
              >
                <RIcon size={11} className="flex-shrink-0 text-brand-500" />
                <span className="truncate">{r.title}</span>
                {r.level === 'advanced' && <span className="text-[8px] px-1 bg-purple-50 text-purple-600 rounded">Advanced</span>}
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SubtopicProjectTag({ subject, nodeId }) {
  const [link, setLink] = useState(null);
  useEffect(() => {
    let cancelled = false;
    api.getNodeProjectLink(subject, nodeId)
      .then(res => { if (!cancelled && res?.project_part) setLink(res.project_part); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [subject, nodeId]);

  if (!link) return null;
  return (
    <p className="text-[10px] text-indigo-600 mt-0.5 flex items-center gap-1">
      <Rocket size={10} /> {link}
    </p>
  );
}

function CheatSheetBtn({ topic }) {
  const [loading, setLoading] = useState(false);
  const [sheet, setSheet] = useState(null);
  const [show, setShow] = useState(false);

  const generate = async (e) => {
    e.stopPropagation();
    if (sheet) { setShow(!show); return; }
    setLoading(true);
    try {
      const res = await api.generateCheatsheet(topic);
      setSheet(res);
      setShow(true);
    } catch (err) {
      alert(err.message || 'Failed to generate cheat sheet');
    } finally { setLoading(false); }
  };

  const downloadPdf = async () => {
    try {
      const blob = await api.getCheatsheetPdf(topic);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      alert(err.message || 'PDF not ready');
    }
  };

  return (
    <>
      <span onClick={generate}
        className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 hover:bg-blue-100 cursor-pointer flex items-center gap-0.5"
        title="Smart cheat sheet">
        {loading ? <span className="animate-spin">⏳</span> : <ScrollText size={10} />}
        sheet
      </span>
      {show && sheet && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShow(false)}>
          <div className="bg-white rounded-2xl max-w-lg w-full max-h-[80vh] overflow-y-auto p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-gray-900">{sheet.title || topic}</h3>
            {sheet.key_formulas?.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-blue-700 mb-1">Key Formulas</h4>
                <ul className="text-sm text-gray-700 space-y-1">{sheet.key_formulas.map((f, i) => <li key={i}>• {f}</li>)}</ul>
              </div>
            )}
            {sheet.key_definitions?.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-blue-700 mb-1">Key Definitions</h4>
                {sheet.key_definitions.map((d, i) => (
                  <p key={i} className="text-sm"><b>{d.term || d}</b>: {d.definition || ''}</p>
                ))}
              </div>
            )}
            {sheet.must_remember?.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-green-700 mb-1">Must Remember</h4>
                <ul className="text-sm text-gray-700 space-y-1">{sheet.must_remember.map((m, i) => <li key={i}>★ {m}</li>)}</ul>
              </div>
            )}
            {sheet.your_gotchas?.length > 0 && (
              <div className="bg-red-50 rounded-lg p-3">
                <h4 className="text-sm font-semibold text-red-700 mb-1">Your Personal Gotchas</h4>
                <ul className="text-sm text-red-800 space-y-1">{sheet.your_gotchas.map((g, i) => <li key={i}>⚠ {g}</li>)}</ul>
              </div>
            )}
            {sheet.quick_examples?.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-purple-700 mb-1">Quick Examples</h4>
                {sheet.quick_examples.map((ex, i) => (
                  <div key={i} className="text-sm mb-2">
                    <p><b>Q:</b> {ex.problem || ex}</p>
                    {ex.solution && <p><b>A:</b> {ex.solution}</p>}
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2 pt-2 border-t">
              <button onClick={downloadPdf}
                className="text-sm bg-brand-500 text-white px-4 py-2 rounded-lg hover:bg-brand-600">Download PDF</button>
              <button onClick={() => { setSheet(null); generate({stopPropagation:()=>{}}); }}
                className="text-sm bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200">Refresh</button>
              <button onClick={() => setShow(false)}
                className="text-sm text-gray-500 px-4 py-2 ml-auto">Close</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function TopicGroup({ topic, subtopics, onStart, onSkip, onComplete, subject, hasProject }) {
  const [open, setOpen] = useState(
    topic.status === 'in_progress' || subtopics.some(s => s.status === 'in_progress')
  );
  const st = STATUS_STYLES[topic.status] || STATUS_STYLES.not_started;
  const Icon = st.icon;

  const doneSubs = subtopics.filter(s => s.status === 'done' || s.status === 'skipped').length;

  return (
    <div className={`rounded-xl border ${st.border} overflow-hidden`}>
      {/* Topic header */}
      <button
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center gap-3 px-4 py-3 ${st.bg} hover:brightness-95 transition-all`}
      >
        <Icon size={18} className={st.iconColor} />
        <span className={`font-semibold text-sm flex-1 text-left ${st.text}`}>{topic.title}</span>
        <span className="text-xs text-gray-400">{doneSubs}/{subtopics.length}</span>
        <span className="text-xs text-gray-400 ml-1">
          {Math.round(topic.mastery * 100)}%
        </span>
        {(topic.status === 'in_progress' || topic.status === 'done') && (
          <CheatSheetBtn topic={topic.title} />
        )}
        {open ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
      </button>

      {/* Topic-level reference resources (video / article / paper) */}
      {open && (
        <div className="px-4 py-2 border-b border-gray-100 bg-gray-50/60">
          <ResourceLinks subject={subject} nodeId={topic.node_id} />
        </div>
      )}

      {/* Subtopics */}
      {open && subtopics.length > 0 && (
        <div className="divide-y divide-gray-100 bg-white">
          {subtopics.map((sub) => {
            const ss = STATUS_STYLES[sub.status] || STATUS_STYLES.not_started;
            const SubIcon = ss.icon;
            const canStart = sub.status === 'in_progress' || sub.status === 'not_started';
            const canSkip = sub.status !== 'done' && sub.status !== 'skipped';

            return (
              <div key={sub.node_id} className="px-5 py-2.5">
                <div className="flex items-center gap-3">
                <SubIcon size={16} className={ss.iconColor} />
                <div className="flex-1 min-w-0">
                  <span className={`text-sm ${ss.text}`}>{sub.title}</span>
                  {hasProject && (sub.status === 'in_progress' || sub.status === 'done') && (
                    <SubtopicProjectTag subject={subject} nodeId={sub.node_id} />
                  )}
                  <ResourceLinks subject={subject} nodeId={sub.node_id} />
                </div>
                {sub.needs_review && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-medium" title="Mastery has decayed — review recommended">
                    review
                  </span>
                )}
                <span className="text-xs text-gray-400">{Math.round(sub.mastery * 100)}%</span>

                {canStart && (
                  <button
                    onClick={() => onStart(sub.title)}
                    className="text-xs px-2.5 py-1 rounded-lg bg-brand-50 text-brand-700 hover:bg-brand-100 font-medium transition-colors"
                  >
                    {sub.status === 'in_progress' ? 'Continue' : 'Start'}
                  </button>
                )}
                {canSkip && (
                  <button
                    onClick={() => onComplete(sub.node_id, sub.title)}
                    className="text-xs px-2 py-1 rounded-lg text-gray-400 hover:bg-green-50 hover:text-green-600 transition-colors"
                    title="Mark as complete"
                  >
                    <CheckCircle2 size={14} />
                  </button>
                )}
                {canSkip && (
                  <button
                    onClick={() => onSkip(sub.node_id, sub.title)}
                    className="text-xs px-2 py-1 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
                    title="Skip this topic"
                  >
                    <SkipForward size={14} />
                  </button>
                )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function BranchChoiceCard({ choiceNode, branches, onChoose, choosing }) {
  return (
    <div className="rounded-xl border-2 border-indigo-200 bg-indigo-50/50 p-5 space-y-3">
      <div className="flex items-center gap-2">
        <GitBranch size={20} className="text-indigo-500" />
        <h3 className="font-bold text-gray-900">{choiceNode.title}</h3>
      </div>
      <p className="text-sm text-gray-600">Pick your track — this is a one-time choice that shapes your curriculum.</p>
      <div className="grid gap-2">
        {branches.map(b => (
          <button
            key={b.node_id}
            onClick={() => onChoose(b)}
            disabled={choosing}
            className="w-full text-left px-4 py-3 rounded-xl border border-indigo-200 bg-white hover:border-indigo-400 hover:bg-indigo-50 transition-all flex items-center gap-3 disabled:opacity-50"
          >
            <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold text-sm flex-shrink-0">
              {b.title.charAt(0)}
            </div>
            <span className="font-medium text-gray-800">{b.title}</span>
            <ChevronRight size={16} className="ml-auto text-gray-400" />
          </button>
        ))}
      </div>
    </div>
  );
}

export default function CurriculumMap() {
  const { subject } = useParams();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);
  const [skipConfirm, setSkipConfirm] = useState(null); // {nodeId, title, warnings}
  const [project, setProject] = useState(null);
  const [projectLoading, setProjectLoading] = useState(false);
  const [choosing, setChoosing] = useState(false);

  const loadProject = async () => {
    setProjectLoading(true);
    try {
      const p = await api.getProject(subject);
      setProject(p);
    } catch (e) {
      // Project not generated yet — OK
      console.log('No project yet');
    } finally { setProjectLoading(false); }
  };

  const load = async () => {
    try {
      const res = await api.getCurriculum(subject);
      setData(res);
      setError(null);
    } catch (e) {
      // Not started yet — try starting
      if (!starting) {
        setStarting(true);
        try {
          const res = await api.startSubject(subject);
          setData(res);
          setError(null);
        } catch (err) {
          console.error('Failed to start subject:', err);
          setError(err?.message || 'Failed to load curriculum. Check if the backend server is running and LLM API keys are configured.');
        } finally {
          setStarting(false);
        }
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); loadProject(); }, [subject]);

  const handleStart = (topicTitle) => {
    navigate('/tutor', { state: { topic: topicTitle, subject } });
  };

  const handleSkipRequest = async (nodeId, title) => {
    // Check for warnings first
    try {
      const res = await api.skipNode(subject, nodeId);
      if (res.warnings && res.warnings.length > 0) {
        setSkipConfirm({ nodeId, title, warnings: res.warnings, done: true });
      }
      // Reload map
      await load();
    } catch (e) {
      console.error('Skip failed:', e);
    }
  };

  const handleComplete = async (nodeId, title) => {
    if (!window.confirm(`Mark "${title}" as complete? This unlocks topics that depend on it.`)) return;
    try {
      await api.completeNode(subject, nodeId);
      await load();
    } catch (e) {
      console.error('Complete failed:', e);
      alert(e.message || 'Could not mark complete');
    }
  };

  const handleChooseBranch = async (branchGroup, branch) => {
    setChoosing(true);
    try {
      await api.chooseBranch(subject, branchGroup, branch.node_id);
      await load();
    } catch (e) {
      console.error('Branch choice failed:', e);
    } finally {
      setChoosing(false);
    }
  };

  const handleContinue = () => {
    if (!data?.stats?.current_node_id || !data?.nodes) return;
    const current = data.nodes.find(n => n.node_id === data.stats.current_node_id);
    if (current) {
      navigate('/tutor', { state: { topic: current.title, subject } });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-8 w-8 border-4 border-brand-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!data || !data.nodes?.length) {
    return (
      <div className="max-w-lg mx-auto px-4 py-12 text-center">
        <AlertTriangle size={32} className="mx-auto text-amber-500 mb-3" />
        <p className="text-gray-700 font-medium">Could not load curriculum for this subject.</p>
        {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
        <p className="text-gray-400 text-xs mt-2">Check server logs for details. Common causes: LLM API keys not set, all models timed out, or server not running.</p>
        <div className="flex gap-3 justify-center mt-4">
          <button onClick={() => { setLoading(true); setError(null); load(); }} className="btn-primary">Retry</button>
          <button onClick={() => navigate('/learn')} className="btn-secondary">Back to Subjects</button>
        </div>
      </div>
    );
  }

  // Group nodes: level-1 topics with their level-2 subtopics
  const topics = data.nodes.filter(n => n.level === 1 && n.node_type !== 'branch');
  const subtopicsByParent = {};
  for (const n of data.nodes) {
    if (n.level === 2) {
      if (!subtopicsByParent[n.parent_id]) subtopicsByParent[n.parent_id] = [];
      subtopicsByParent[n.parent_id].push(n);
    }
  }

  // Collect choice nodes and their branch options
  const choiceNodes = data.nodes.filter(n => n.node_type === 'choice');
  const pendingChoices = data.pending_choices || [];
  const chosenBranches = data.chosen_branches || {};

  // For chosen branches, treat them like regular topics
  const chosenBranchNodes = data.nodes.filter(
    n => n.node_type === 'branch' && Object.values(chosenBranches).includes(n.node_id)
  );

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-4">
      {/* Back + Continue */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/learn')} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1" />
        {data.stats?.current_node_id && (
          <button
            onClick={handleContinue}
            className="btn-primary text-sm flex items-center gap-1.5 px-4 py-2"
          >
            <Play size={16} /> Continue Learning
          </button>
        )}
      </div>

      <ProgressHeader stats={data.stats} subjectTitle={data.subject_title} />

      {/* Project Brief (N13) */}
      {project && project.title && (
        <ProjectBrief project={project} subject={subject} onUpdate={() => { load(); loadProject(); }} />
      )}
      {!project && !projectLoading && (
        <button
          onClick={loadProject}
          className="w-full py-3 rounded-xl border-2 border-dashed border-indigo-200 text-indigo-600 text-sm font-medium hover:bg-indigo-50 transition-colors flex items-center justify-center gap-2"
        >
          <Rocket size={16} /> Generate Capstone Project
        </button>
      )}
      {projectLoading && (
        <div className="flex items-center justify-center py-4">
          <div className="animate-spin h-6 w-6 border-3 border-indigo-500 border-t-transparent rounded-full" />
          <span className="ml-2 text-sm text-gray-500">Generating project...</span>
        </div>
      )}

      {/* Topic tree */}
      <div className="space-y-3">
        {/* Render all level-1 nodes in order, inserting choice cards where needed */}
        {data.nodes
          .filter(n => n.level === 1)
          .sort((a, b) => a.order - b.order)
          .map(node => {
            // Choice node with pending decision
            if (node.node_type === 'choice' && pendingChoices.includes(node.branch_group || node.node_id)) {
              const branches = data.nodes.filter(
                n => n.node_type === 'branch' && n.parent_id === node.node_id
              );
              // Also check branch_group from the node_id of the choice node
              const bg = branches[0]?.branch_group || node.node_id;
              if (pendingChoices.includes(bg)) {
                return (
                  <BranchChoiceCard
                    key={node.node_id}
                    choiceNode={node}
                    branches={branches}
                    onChoose={(b) => handleChooseBranch(bg, b)}
                    choosing={choosing}
                  />
                );
              }
            }

            // Choice node already resolved — show chosen branch as a TopicGroup
            if (node.node_type === 'choice') {
              const bg = node.node_id;
              const chosenId = chosenBranches[bg];
              const chosenBranch = chosenBranchNodes.find(n => n.node_id === chosenId);
              if (chosenBranch) {
                return (
                  <TopicGroup
                    key={chosenBranch.node_id}
                    topic={chosenBranch}
                    subtopics={subtopicsByParent[chosenBranch.node_id] || []}
                    onStart={handleStart}
                    onSkip={handleSkipRequest}
                    onComplete={handleComplete}
                    subject={subject}
                    hasProject={!!project?.title}
                  />
                );
              }
              return null;
            }

            // Skip branch nodes (handled via choice)
            if (node.node_type === 'branch') return null;

            // Regular topic
            return (
              <TopicGroup
                key={node.node_id}
                topic={node}
                subtopics={subtopicsByParent[node.node_id] || []}
                onStart={handleStart}
                onSkip={handleSkipRequest}
                onComplete={handleComplete}
                subject={subject}
                hasProject={!!project?.title}
              />
            );
          })}
      </div>

      {/* Skip confirmation toast */}
      {skipConfirm && (
        <div className="fixed bottom-20 inset-x-4 max-w-lg mx-auto bg-amber-50 border border-amber-300 rounded-xl p-4 shadow-lg z-50">
          <div className="flex items-start gap-3">
            <AlertTriangle size={20} className="text-amber-500 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800">Skipped "{skipConfirm.title}"</p>
              {skipConfirm.warnings.map((w, i) => (
                <p key={i} className="text-xs text-amber-600 mt-1">{w}</p>
              ))}
            </div>
            <button onClick={() => setSkipConfirm(null)} className="text-amber-400 hover:text-amber-600">
              &times;
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
