import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { NotebookPen, Trash2, Edit3, Check, X, ChevronDown, ChevronRight, Link2, Download } from 'lucide-react';

function NoteCard({ note, onDelete, onUpdate }) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(note.user_note || '');
  const [deleting, setDeleting] = useState(false);

  const handleSave = async () => {
    await onUpdate(note.note_id, editText);
    setEditing(false);
  };

  const handleDelete = async () => {
    setDeleting(true);
    try { await onDelete(note.note_id); }
    finally { setDeleting(false); }
  };

  const timeAgo = () => {
    const hrs = (Date.now() / 1000 - note.created_at) / 3600;
    if (hrs < 1) return 'Just now';
    if (hrs < 24) return `${Math.round(hrs)}h ago`;
    return `${Math.round(hrs / 24)}d ago`;
  };

  return (
    <div className="border rounded-xl overflow-hidden bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-gray-50/50 transition-colors"
      >
        <div className="w-1 h-8 rounded-full bg-teal-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-900 line-clamp-2">{note.selected_text}</p>
          <div className="flex items-center gap-2 mt-1">
            {note.topic && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-teal-50 text-teal-700 capitalize">
                {note.topic}
              </span>
            )}
            <span className="text-[10px] text-gray-400">{timeAgo()}</span>
          </div>
        </div>
        {open ? <ChevronDown size={16} className="text-gray-400 mt-1" /> : <ChevronRight size={16} className="text-gray-400 mt-1" />}
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-3">
          {/* Highlighted text */}
          <div className="bg-teal-50 border border-teal-200 rounded-lg p-3">
            <p className="text-xs font-semibold text-teal-700 mb-1">Highlighted</p>
            <p className="text-sm text-teal-900">{note.selected_text}</p>
          </div>

          {/* User note */}
          {editing ? (
            <div className="space-y-2">
              <textarea
                value={editText}
                onChange={e => setEditText(e.target.value)}
                rows={3}
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-teal-300 resize-none"
                placeholder="Add your notes..."
              />
              <div className="flex gap-2">
                <button onClick={handleSave} className="flex items-center gap-1 text-xs px-3 py-1.5 bg-teal-600 text-white rounded-lg">
                  <Check size={12} /> Save
                </button>
                <button onClick={() => setEditing(false)} className="flex items-center gap-1 text-xs px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg">
                  <X size={12} /> Cancel
                </button>
              </div>
            </div>
          ) : (
            <div>
              {note.user_note ? (
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs font-semibold text-gray-500 mb-1">Your notes</p>
                  <p className="text-sm text-gray-700">{note.user_note}</p>
                </div>
              ) : null}
              <button
                onClick={() => setEditing(true)}
                className="text-xs text-teal-600 hover:text-teal-700 mt-1 flex items-center gap-1"
              >
                <Edit3 size={10} /> {note.user_note ? 'Edit note' : 'Add a note'}
              </button>
            </div>
          )}

          {/* Related topics */}
          {note.related_topics?.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase mb-1">Related Topics</p>
              <div className="flex flex-wrap gap-1">
                {note.related_topics.map((t, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full flex items-center gap-0.5 capitalize">
                    <Link2 size={8} /> {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Delete */}
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="text-xs text-red-400 hover:text-red-600 flex items-center gap-1 disabled:opacity-50"
          >
            <Trash2 size={12} /> {deleting ? 'Removing...' : 'Remove'}
          </button>
        </div>
      )}
    </div>
  );
}

export default function Notebook() {
  const [notes, setNotes] = useState([]);
  const [topics, setTopics] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.getNotebook(filter || null);
      setNotes(data.notes || []);
      setTotal(data.total || 0);
      setTopics(data.topics || []);
    } catch (e) {
      console.error('Failed to load notebook:', e);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [filter]);

  const handleDelete = async (noteId) => {
    await api.deleteNote(noteId);
    setNotes(prev => prev.filter(n => n.note_id !== noteId));
    setTotal(prev => Math.max(0, prev - 1));
  };

  const handleUpdate = async (noteId, userNote) => {
    await api.updateNote(noteId, userNote);
    setNotes(prev => prev.map(n =>
      n.note_id === noteId ? { ...n, user_note: userNote } : n
    ));
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <NotebookPen size={20} className="text-teal-600" />
            My Notebook
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            {total > 0 ? `${total} note${total > 1 ? 's' : ''} saved` : 'Highlight text in lessons to save notes'}
          </p>
        </div>
        {total > 0 && (
          <button
            onClick={async () => {
              try {
                const blob = await api.downloadNotebookPdf();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'my_notebook.pdf';
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
              } catch (e) {
                alert(e.message || 'Export failed');
              }
            }}
            className="btn-secondary text-sm flex items-center gap-1.5 py-2 px-3"
          >
            <Download size={16} /> Export PDF
          </button>
        )}
      </div>

      {/* Topic filter */}
      {topics.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setFilter('')}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
              !filter ? 'bg-teal-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
          >
            All
          </button>
          {topics.map(t => (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors capitalize ${
                filter === t ? 'bg-teal-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {/* Notes list */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin h-8 w-8 border-4 border-teal-500 border-t-transparent rounded-full" />
        </div>
      ) : notes.length === 0 ? (
        <div className="text-center py-12">
          <div className="w-16 h-16 bg-teal-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <NotebookPen size={32} className="text-teal-400" />
          </div>
          <p className="text-gray-500 text-sm">
            {filter ? 'No notes for this topic.' : 'No notes yet. Select text during a lesson and tap "Save to notebook"!'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {notes.map(n => (
            <NoteCard key={n.note_id} note={n} onDelete={handleDelete} onUpdate={handleUpdate} />
          ))}
        </div>
      )}
    </div>
  );
}
