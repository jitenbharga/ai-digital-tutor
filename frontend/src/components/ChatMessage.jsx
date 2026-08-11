import { useState } from 'react';
import ModeBadge from './ModeBadge';
import Markdown from './Markdown';
import { api } from '../lib/api';

const RE_EXPLAIN_STYLES = [
  { key: 'simpler', label: 'Simpler', icon: '🔤' },
  { key: 'analogy', label: 'Analogy', icon: '🔗' },
  { key: 'worked_example', label: 'Example', icon: '📝' },
  { key: 'step_by_step', label: 'Step by step', icon: '🪜' },
];

function ExplanationBlock({ explanation }) {
  if (!explanation) return null;
  return (
    <div className="bg-brand-50 border border-brand-100 rounded-lg p-4 mt-3 space-y-2 text-sm">
      {explanation.core_concept && (
        <div><span className="font-semibold text-brand-700">Core concept:</span> {explanation.core_concept}</div>
      )}
      {explanation.intuition && (
        <div><span className="font-semibold text-brand-700">Intuition:</span> {explanation.intuition}</div>
      )}
      {explanation.step_by_step?.length > 0 && (
        <div>
          <span className="font-semibold text-brand-700">Steps:</span>
          <ol className="list-decimal list-inside ml-2 mt-1 space-y-1">
            {explanation.step_by_step.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
        </div>
      )}
    </div>
  );
}

function FeedbackBlock({ feedback }) {
  return (
    <div className={`rounded-lg p-4 mt-3 text-sm space-y-2 ${feedback.correct ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
      <div className="flex items-center gap-2 font-semibold">
        <span className="text-lg">{feedback.correct ? '✅' : '❌'}</span>
        <span>{feedback.correct ? 'Correct!' : 'Not quite right'}</span>
        <span className="ml-auto text-xs font-normal text-gray-500">Score: {(feedback.score * 100).toFixed(0)}%</span>
      </div>
      {feedback.reasoning && <div><span className="font-medium">Reasoning:</span> {feedback.reasoning}</div>}
      {feedback.targeted_feedback && <div><span className="font-medium">Feedback:</span> {feedback.targeted_feedback}</div>}
      {feedback.remediation && <div className="text-gray-600"><span className="font-medium">Remediation:</span> {feedback.remediation}</div>}
      {feedback.misconception && !feedback.misconception_probe && (
        <div className="text-orange-700"><span className="font-medium">Misconception:</span> {feedback.misconception}</div>
      )}
      {feedback.misconception_probe && (
        <div className="mt-3 bg-indigo-50 border border-indigo-200 rounded-lg p-3 space-y-1">
          <div className="font-semibold text-indigo-800 text-xs uppercase tracking-wide">Think about it</div>
          <div className="text-indigo-900">{feedback.misconception_probe.probe}</div>
          {feedback.misconception_probe.follow_up_if_stuck && (
            <details className="text-xs text-indigo-600 cursor-pointer mt-1">
              <summary>Stuck? Get a nudge</summary>
              <p className="mt-1">{feedback.misconception_probe.follow_up_if_stuck}</p>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

export default function ChatMessage({ message, onReExplain }) {
  const { role, content, mode, explanation, feedback, streaming, hint, reExplain } = message;
  const [reExplaining, setReExplaining] = useState(false);

  const handleReExplain = async (style) => {
    if (onReExplain) {
      setReExplaining(true);
      try { await onReExplain(style); } finally { setReExplaining(false); }
    }
  };

  if (role === 'user') {
    return (
      <div className="flex justify-end min-w-0">
        <div className="bg-brand-600 text-white rounded-2xl rounded-br-md px-4 py-3 max-w-lg shadow-sm min-w-0">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start min-w-0">
      <div className="bg-white rounded-2xl rounded-bl-md px-5 py-4 max-w-2xl shadow-sm border border-gray-100 min-w-0">
        {mode && <ModeBadge mode={mode} />}
        {reExplain && (
          <span className="inline-block text-xs px-2 py-0.5 rounded bg-brand-50 text-brand-600 font-medium mb-1">
            {RE_EXPLAIN_STYLES.find(s => s.key === reExplain.style)?.icon || '🔄'} {(reExplain.style || '').replace('_', ' ')}
          </span>
        )}
        <div className={`mt-2 prose prose-sm max-w-none min-w-0 ${streaming ? 'streaming-cursor' : ''}`}>
          <Markdown streaming={streaming}>{content}</Markdown>
        </div>
        {explanation && <ExplanationBlock explanation={explanation} />}
        {feedback && <FeedbackBlock feedback={feedback} />}
        {hint && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mt-3 text-sm">
            <span className="font-semibold text-yellow-800">💡 Hint:</span> {hint}
          </div>
        )}
        {reExplain?.check_understanding && (
          <div className="mt-2 bg-green-50 border border-green-200 rounded-lg p-2">
            <p className="text-xs text-green-800">{reExplain.check_understanding}</p>
          </div>
        )}
        {/* N2: Re-explain buttons on tutor explanation messages */}
        {role === 'tutor' && content && !feedback && !hint && !streaming && !reExplain && onReExplain && (
          <div className="mt-3 flex flex-wrap gap-2 border-t border-gray-100 pt-3">
            <span className="text-xs text-gray-400 self-center mr-1">Didn't get it?</span>
            {RE_EXPLAIN_STYLES.map(s => (
              <button
                key={s.key}
                onClick={() => handleReExplain(s.key)}
                disabled={reExplaining}
                className="text-xs px-2.5 py-1.5 rounded-lg bg-gray-50 hover:bg-brand-50 hover:text-brand-700 text-gray-600 border border-gray-200 transition-colors disabled:opacity-50 flex items-center gap-1"
              >
                <span>{s.icon}</span> {s.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
