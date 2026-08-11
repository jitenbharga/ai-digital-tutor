import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { Upload, FileText, Trash2, MessageCircle, GraduationCap, Send, X, Loader2, AlertTriangle } from 'lucide-react';
import Markdown from '../components/Markdown';

function AskChat({ materialId, title, onClose }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = async () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: q }]);
    setLoading(true);
    try {
      const res = await api.askMaterial(materialId, q);
      let reply = res.answer || 'No answer';
      if (res.covered === false) reply = '⚠️ ' + reply;
      if (res.follow_up) reply += '\n\n💡 ' + res.follow_up;
      setMessages(prev => [...prev, { role: 'tutor', text: reply }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'tutor', text: '❌ ' + (e.message || 'Failed') }]);
    } finally { setLoading(false); }
  };

  return (
    <div className="border border-blue-200 rounded-xl bg-blue-50/30 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-blue-800">Ask about: {title}</h4>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
      </div>
      <div className="max-h-64 overflow-y-auto space-y-2 text-sm">
        {messages.map((m, i) => (
          <div key={i} className={`${m.role === 'user' ? 'text-right' : 'text-left'}`}>
            <div className={`inline-block max-w-[85%] px-3 py-2 rounded-xl ${m.role === 'user' ? 'bg-brand-500 text-white' : 'bg-white border border-gray-200'}`}>
              <Markdown>{m.text}</Markdown>
            </div>
          </div>
        ))}
        {loading && <div className="text-gray-400 text-xs animate-pulse">Thinking...</div>}
        <div ref={endRef} />
      </div>
      <div className="flex gap-2">
        <input
          value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="Ask about this chapter..."
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <button onClick={send} disabled={loading || !input.trim()}
          className="bg-brand-500 text-white px-3 py-2 rounded-lg hover:bg-brand-600 disabled:opacity-50">
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}

export default function Materials() {
  const navigate = useNavigate();
  const [materials, setMaterials] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [askingId, setAskingId] = useState(null);
  const [quizzing, setQuizzing] = useState(null);
  const fileRef = useRef(null);

  const load = async () => {
    try {
      const res = await api.getMaterials();
      setMaterials(res.materials || []);
    } catch (e) {
      setError(e.message);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadMaterial(file, file.name.replace(/\.[^.]+$/, ''));
      await load();
    } catch (err) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const deleteMaterial = async (id) => {
    if (!confirm('Delete this material?')) return;
    try {
      await api.deleteMaterial(id);
      setMaterials(prev => prev.filter(m => m.material_id !== id));
    } catch (e) { setError(e.message); }
  };

  const startQuiz = async (mat) => {
    setQuizzing(mat.material_id);
    try {
      const res = await api.quizFromMaterial(mat.material_id);
      // Hand the generated quiz to the Quiz page via router state
      navigate('/quiz', { state: { quiz: res } });
    } catch (e) {
      setError(e.message || 'Failed to generate quiz');
    } finally { setQuizzing(null); }
  };

  if (loading) {
    return (
      <div className="max-w-lg mx-auto px-4 py-6 space-y-5 animate-fade-in">
        <div className="skeleton h-10 w-48 mx-auto" />
        <div className="skeleton h-32 w-full rounded-2xl" />
        <div className="skeleton h-20 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-6 space-y-6 animate-fade-in">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-600 text-white rounded-2xl mb-3 shadow-soft">
          <FileText size={26} />
        </div>
        <h2 className="text-2xl font-extrabold text-ink">My Chapters</h2>
        <p className="text-ink-muted text-sm mt-1">Upload your textbook — learn & get quizzed on YOUR syllabus</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 flex items-start gap-2">
          <AlertTriangle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
          <p className="text-red-700 text-sm flex-1">{error}</p>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600"><X size={14} /></button>
        </div>
      )}

      {/* Upload dropzone */}
      <div className="bg-gradient-to-br from-brand-50/50 to-white rounded-2xl border-2 border-dashed border-brand-200 p-8 text-center hover:border-brand-400 hover:bg-brand-50/60 transition-all">
        <input ref={fileRef} type="file" accept=".pdf,.txt,.md" onChange={upload} className="hidden" />
        <button onClick={() => fileRef.current?.click()} disabled={uploading}
          className="flex flex-col items-center gap-2 mx-auto text-ink-muted hover:text-brand-600 disabled:opacity-60">
          <span className="w-12 h-12 rounded-2xl bg-white shadow-soft flex items-center justify-center">
            {uploading ? <Loader2 size={24} className="animate-spin text-brand-500" /> : <Upload size={24} className="text-brand-500" />}
          </span>
          <span className="text-sm font-semibold text-ink-soft">{uploading ? 'Reading your chapter…' : 'Upload PDF, TXT, or MD'}</span>
          <span className="text-xs text-ink-faint">Max 5 MB · up to 10 files · text-based PDFs</span>
        </button>
      </div>

      {/* Materials list */}
      {materials.length === 0 ? (
        <div className="text-center py-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-slate-100 text-slate-300 mb-3"><FileText size={26} /></div>
          <p className="text-ink-muted text-sm">No chapters yet — upload your first one above.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {materials.map(mat => (
            <div key={mat.material_id} className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <FileText size={18} className="text-brand-500" />
                  <div>
                    <h3 className="font-semibold text-gray-900 text-sm">{mat.title}</h3>
                    <p className="text-xs text-gray-400">{mat.chunk_count} chunks · {Math.round((mat.char_count || 0) / 1000)}k chars</p>
                  </div>
                </div>
                <button onClick={() => deleteMaterial(mat.material_id)}
                  className="text-gray-300 hover:text-red-500 transition-colors">
                  <Trash2 size={16} />
                </button>
              </div>

              <div className="flex gap-2">
                <button onClick={() => setAskingId(askingId === mat.material_id ? null : mat.material_id)}
                  className="flex items-center gap-1.5 text-xs bg-blue-50 text-blue-700 px-3 py-1.5 rounded-lg hover:bg-blue-100">
                  <MessageCircle size={14} /> Ask
                </button>
                <button onClick={() => startQuiz(mat)} disabled={quizzing === mat.material_id}
                  className="flex items-center gap-1.5 text-xs bg-green-50 text-green-700 px-3 py-1.5 rounded-lg hover:bg-green-100 disabled:opacity-50">
                  {quizzing === mat.material_id ? <Loader2 size={14} className="animate-spin" /> : <GraduationCap size={14} />}
                  Quiz me
                </button>
              </div>

              {askingId === mat.material_id && (
                <AskChat materialId={mat.material_id} title={mat.title} onClose={() => setAskingId(null)} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
