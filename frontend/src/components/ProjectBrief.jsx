import { useState } from 'react';
import { api } from '../lib/api';
import {
  Rocket, CheckCircle2, Circle, ChevronDown, ChevronRight,
  Send, Code, FileText, Link, Star, AlertTriangle, Trophy,
} from 'lucide-react';

const TYPE_BADGE = {
  technical: { label: 'Capstone Project', bg: 'bg-indigo-50', text: 'text-indigo-700', icon: Code },
  non_technical: { label: 'Applied Task', bg: 'bg-amber-50', text: 'text-amber-700', icon: FileText },
};

const SUBMIT_TYPES = [
  { value: 'description', label: 'Description', icon: FileText },
  { value: 'code', label: 'Code', icon: Code },
  { value: 'link', label: 'Link / Repo', icon: Link },
];

function MilestoneItem({ ms, subject, onComplete }) {
  const [completing, setCompleting] = useState(false);

  const handleComplete = async () => {
    setCompleting(true);
    try {
      await api.completeMilestone(subject, ms.milestone_id);
      onComplete(ms.milestone_id);
    } finally { setCompleting(false); }
  };

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg transition-colors ${
      ms.completed ? 'bg-green-50' : 'bg-gray-50'
    }`}>
      {ms.completed ? (
        <CheckCircle2 size={18} className="text-green-500 mt-0.5 flex-shrink-0" />
      ) : (
        <button
          onClick={handleComplete}
          disabled={completing}
          className="mt-0.5 flex-shrink-0 hover:text-green-500 transition-colors disabled:opacity-50"
        >
          <Circle size={18} className="text-gray-300" />
        </button>
      )}
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium ${ms.completed ? 'text-green-700 line-through' : 'text-gray-900'}`}>
          {ms.title}
        </p>
        {ms.description && (
          <p className="text-xs text-gray-500 mt-0.5">{ms.description}</p>
        )}
      </div>
    </div>
  );
}

function ReviewResult({ review }) {
  if (!review) return null;
  const scoreColor = review.overall_score >= 80 ? 'text-green-600' :
    review.overall_score >= 60 ? 'text-amber-600' : 'text-red-600';

  return (
    <div className="space-y-4 mt-4">
      <div className="flex items-center gap-3">
        <Trophy size={24} className={scoreColor} />
        <div>
          <p className={`text-2xl font-bold ${scoreColor}`}>{Math.round(review.overall_score)}%</p>
          <p className="text-xs text-gray-500">
            {review.passed ? 'Passed — great work!' : 'Keep going — you\'re learning!'}
          </p>
        </div>
      </div>

      {review.summary && (
        <p className="text-sm text-gray-700 bg-blue-50 rounded-lg p-3">{review.summary}</p>
      )}

      {review.milestone_reviews?.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-gray-500 uppercase">Milestone Review</p>
          {review.milestone_reviews.map(mr => (
            <div key={mr.milestone_id} className={`p-3 rounded-lg border ${
              mr.passed ? 'border-green-200 bg-green-50/50' : 'border-red-200 bg-red-50/50'
            }`}>
              <div className="flex items-center gap-2">
                {mr.passed ? <CheckCircle2 size={14} className="text-green-500" /> : <AlertTriangle size={14} className="text-red-400" />}
                <span className="text-sm font-medium">{mr.title}</span>
              </div>
              {mr.feedback && <p className="text-xs text-gray-600 mt-1 ml-5">{mr.feedback}</p>}
            </div>
          ))}
        </div>
      )}

      {review.strengths?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-green-600 uppercase mb-1">Strengths</p>
          {review.strengths.map((s, i) => (
            <p key={i} className="text-sm text-gray-700 flex items-start gap-1.5">
              <Star size={12} className="text-green-400 mt-0.5 flex-shrink-0" /> {s}
            </p>
          ))}
        </div>
      )}

      {review.improvements?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-amber-600 uppercase mb-1">To Improve</p>
          {review.improvements.map((s, i) => (
            <p key={i} className="text-sm text-gray-700 flex items-start gap-1.5">
              <AlertTriangle size={12} className="text-amber-400 mt-0.5 flex-shrink-0" /> {s}
            </p>
          ))}
        </div>
      )}

      {review.next_steps && (
        <p className="text-sm text-indigo-700 bg-indigo-50 rounded-lg p-3">
          <span className="font-medium">Next: </span>{review.next_steps}
        </p>
      )}
    </div>
  );
}

export default function ProjectBrief({ project, subject, onUpdate }) {
  const [expanded, setExpanded] = useState(true);
  const [showSubmit, setShowSubmit] = useState(false);
  const [submitType, setSubmitType] = useState('description');
  const [submitContent, setSubmitContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [review, setReview] = useState(project?.review || null);

  if (!project || !project.title) return null;

  const badge = TYPE_BADGE[project.topic_type] || TYPE_BADGE.technical;
  const BadgeIcon = badge.icon;
  const donePct = project.milestones_total > 0
    ? Math.round((project.milestones_done / project.milestones_total) * 100) : 0;

  const handleMilestoneComplete = (milestoneId) => {
    if (onUpdate) onUpdate();
  };

  const handleSubmit = async () => {
    if (!submitContent.trim()) return;
    setSubmitting(true);
    try {
      const result = await api.submitProject(subject, submitType, submitContent);
      setReview(result);
      setShowSubmit(false);
      if (onUpdate) onUpdate();
    } catch (e) {
      console.error('Submit failed:', e);
    } finally { setSubmitting(false); }
  };

  return (
    <div className="border-2 border-indigo-200 rounded-2xl bg-gradient-to-br from-indigo-50/50 to-purple-50/50 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-indigo-50/50 transition-colors"
      >
        <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
          <Rocket size={20} className="text-indigo-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${badge.bg} ${badge.text}`}>
              <BadgeIcon size={10} className="inline mr-0.5" />
              {badge.label}
            </span>
            {project.status === 'reviewed' && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-green-50 text-green-700">Reviewed</span>
            )}
          </div>
          <p className="text-sm font-bold text-gray-900 truncate">{project.title}</p>
          <p className="text-xs text-gray-500">{project.goal}</p>
        </div>
        <div className="text-right mr-2">
          <p className="text-lg font-bold text-indigo-600">{donePct}%</p>
          <p className="text-[10px] text-gray-400">{project.milestones_done}/{project.milestones_total}</p>
        </div>
        {expanded ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-indigo-100 pt-3">
          {/* Description */}
          {project.description && (
            <p className="text-sm text-gray-700 leading-relaxed">{project.description}</p>
          )}

          {/* Skills */}
          {project.skills_required?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {project.skills_required.map((s, i) => (
                <span key={i} className="text-[10px] px-2 py-0.5 bg-white border border-gray-200 rounded-full text-gray-600">
                  {s}
                </span>
              ))}
            </div>
          )}

          {/* Milestones */}
          {project.milestones?.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-gray-500 uppercase">Milestones</p>
              {project.milestones.map(ms => (
                <MilestoneItem
                  key={ms.milestone_id}
                  ms={ms}
                  subject={subject}
                  onComplete={handleMilestoneComplete}
                />
              ))}
            </div>
          )}

          {/* Review result */}
          {review && <ReviewResult review={review} />}

          {/* Submit button / form */}
          {project.status !== 'reviewed' && !showSubmit && (
            <button
              onClick={() => setShowSubmit(true)}
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-xl transition-colors flex items-center justify-center gap-2"
            >
              <Send size={14} /> Submit Project
            </button>
          )}

          {project.status === 'reviewed' && (
            <button
              onClick={() => { setShowSubmit(true); setReview(null); }}
              className="w-full py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium rounded-xl transition-colors"
            >
              Resubmit
            </button>
          )}

          {showSubmit && (
            <div className="space-y-3 bg-white rounded-xl p-3 border border-gray-200">
              <p className="text-sm font-medium text-gray-900">Submit Your Build</p>
              <p className="text-xs text-gray-500">
                This is a best-effort AI review — not a hard pass/fail. Share what you built!
              </p>

              <div className="flex gap-2">
                {SUBMIT_TYPES.map(st => (
                  <button
                    key={st.value}
                    onClick={() => setSubmitType(st.value)}
                    className={`flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                      submitType === st.value ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-500'
                    }`}
                  >
                    <st.icon size={12} /> {st.label}
                  </button>
                ))}
              </div>

              <textarea
                value={submitContent}
                onChange={e => setSubmitContent(e.target.value)}
                rows={6}
                placeholder={
                  submitType === 'code' ? 'Paste your code here...' :
                  submitType === 'link' ? 'Paste your repo URL or link...' :
                  'Describe what you built, how it works, and what you learned...'
                }
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
              />

              <div className="flex gap-2">
                <button
                  onClick={() => setShowSubmit(false)}
                  className="flex-1 py-2 bg-gray-100 text-gray-600 text-sm rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || !submitContent.trim()}
                  className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 flex items-center justify-center gap-1.5"
                >
                  {submitting ? (
                    <><div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" /> Reviewing...</>
                  ) : (
                    <><Send size={14} /> Submit for Review</>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
