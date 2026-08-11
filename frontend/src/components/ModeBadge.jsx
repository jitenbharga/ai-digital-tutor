const MODE_LABELS = {
  direct_question: { label: 'Direct Question', emoji: '📝' },
  socratic_probe: { label: 'Socratic Probe', emoji: '🤔' },
  reveal_step: { label: 'Step-by-Step', emoji: '🔍' },
  challenge: { label: 'Challenge', emoji: '🔥' },
};

export default function ModeBadge({ mode }) {
  const m = MODE_LABELS[mode] || { label: mode, emoji: '📖' };
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold mode-${mode}`}>
      {m.emoji} {m.label}
    </span>
  );
}
