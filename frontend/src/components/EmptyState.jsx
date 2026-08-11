/**
 * Reusable empty-state (W7). The audit flagged that most lists render blank
 * instead of an inviting empty state. Pages pass an optional icon, a title, a
 * message, and an optional action (e.g. a button/link).
 */
export default function EmptyState({ icon: Icon, title, message, action }) {
  return (
    <div
      role="status"
      className="flex flex-col items-center justify-center text-center py-12 px-4"
    >
      {Icon && <Icon className="text-gray-300 mb-3" size={40} aria-hidden="true" />}
      <p className="text-gray-700 font-semibold">{title}</p>
      {message && <p className="text-gray-500 text-sm mt-1 max-w-sm">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
