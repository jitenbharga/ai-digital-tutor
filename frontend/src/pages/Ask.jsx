import { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { api } from '../lib/api';
import { Send, ArrowLeft, Camera, X, RefreshCw } from 'lucide-react';
import Markdown from '../components/Markdown';

const EXPLAIN_STYLES = [
  { key: 'simpler', label: 'Simpler', icon: '🔤' },
  { key: 'analogy', label: 'Analogy', icon: '🔗' },
  { key: 'worked_example', label: 'Example', icon: '📝' },
  { key: 'step_by_step', label: 'Step by step', icon: '🪜' },
];

function AskMessage({ msg, sessionId, onReExplain }) {
  const [reExplaining, setReExplaining] = useState(false);

  const handleReExplain = async (style) => {
    setReExplaining(true);
    try {
      await onReExplain(style, sessionId);
    } finally {
      setReExplaining(false);
    }
  };

  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="bg-brand-600 text-white rounded-2xl rounded-br-md px-4 py-3 max-w-lg shadow-sm">
          <Markdown>{msg.content}</Markdown>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="bg-white rounded-2xl rounded-bl-md px-5 py-4 max-w-2xl shadow-sm border border-gray-100">
        <div className="prose prose-sm max-w-none">
          <Markdown>{msg.content}</Markdown>
        </div>

        {/* Probing question */}
        {msg.probing_question && (
          <div className="mt-3 bg-indigo-50 border border-indigo-200 rounded-lg p-3">
            <p className="text-xs font-semibold text-indigo-700 uppercase tracking-wide mb-1">Think about it</p>
            <p className="text-sm text-indigo-900">{msg.probing_question}</p>
          </div>
        )}

        {/* Hint if stuck */}
        {msg.hint_if_stuck && (
          <details className="mt-2 text-xs text-gray-500 cursor-pointer">
            <summary className="hover:text-brand-600">Stuck? Get a nudge</summary>
            <p className="mt-1 text-sm text-gray-700 bg-yellow-50 rounded-lg p-2">{msg.hint_if_stuck}</p>
          </details>
        )}

        {/* Concept connection */}
        {msg.concept_connection && (
          <p className="mt-2 text-xs text-gray-400 italic">{msg.concept_connection}</p>
        )}

        {/* N2: Re-explain buttons */}
        {msg.role === 'tutor' && !msg.isReExplain && (
          <div className="mt-3 flex flex-wrap gap-2 border-t border-gray-100 pt-3">
            <span className="text-xs text-gray-400 self-center mr-1">Didn't get it?</span>
            {EXPLAIN_STYLES.map(s => (
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

        {/* Style badge for re-explanations */}
        {msg.isReExplain && msg.style && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs px-2 py-0.5 rounded bg-brand-50 text-brand-600 font-medium">
              {EXPLAIN_STYLES.find(s => s.key === msg.style)?.icon} {msg.style.replace('_', ' ')}
            </span>
            {msg.key_takeaway && (
              <span className="text-xs text-gray-500">Key: {msg.key_takeaway}</span>
            )}
          </div>
        )}

        {/* Check understanding */}
        {msg.check_understanding && (
          <div className="mt-2 bg-green-50 border border-green-200 rounded-lg p-2">
            <p className="text-xs text-green-800">{msg.check_understanding}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function Ask() {
  const navigate = useNavigate();
  const location = useLocation();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [currentTopic, setCurrentTopic] = useState(null);
  const [imageText, setImageText] = useState('');
  const [showImageInput, setShowImageInput] = useState(false);
  const [ocrBusy, setOcrBusy] = useState(false);
  const [ocrProgress, setOcrProgress] = useState(0);
  const [ocrError, setOcrError] = useState('');
  const fileInputRef = useRef(null);
  const bottomRef = useRef(null);
  const prefillHandled = useRef(false);

  // Lazy-load tesseract.js from CDN once
  const loadTesseract = () => new Promise((resolve, reject) => {
    if (window.Tesseract) return resolve(window.Tesseract);
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js';
    s.onload = () => resolve(window.Tesseract);
    s.onerror = () => reject(new Error('Could not load OCR library'));
    document.head.appendChild(s);
  });

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting same file
    if (!file) return;
    setOcrError('');
    if (!file.type.startsWith('image/')) { setOcrError('Please select an image file.'); return; }
    if (file.size > 8 * 1024 * 1024) { setOcrError('Image too large (max 8MB).'); return; }
    setOcrBusy(true);
    setOcrProgress(0);
    setShowImageInput(true);
    try {
      const Tesseract = await loadTesseract();
      const { data } = await Tesseract.recognize(file, 'eng', {
        logger: (m) => { if (m.status === 'recognizing text') setOcrProgress(Math.round(m.progress * 100)); },
      });
      const text = (data?.text || '').trim();
      setImageText(text || '');
      if (!text) setOcrError('No text detected — you can type it manually below.');
    } catch (err) {
      setOcrError(err.message || 'OCR failed — paste the text manually below.');
    } finally {
      setOcrBusy(false);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // N8: Handle prefilled text from highlight-to-ask
  useEffect(() => {
    if (location.state?.prefill && !prefillHandled.current) {
      prefillHandled.current = true;
      const prefill = location.state.prefill;
      const ctx = location.state.context || '';
      setInput(ctx ? `About "${prefill}" (from ${ctx}): ` : prefill);
    }
  }, [location.state]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;

    const userMsg = { role: 'user', content: q + (imageText ? `\n\n📷 [Image text attached]` : '') };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const data = await api.ask(q, imageText || null);
      setSessionId(data.session_id || sessionId);
      if (data.topic) setCurrentTopic(data.topic);

      const tutorMsg = {
        role: 'tutor',
        content: data.response,
        probing_question: data.probing_question,
        hint_if_stuck: data.hint_if_stuck,
        concept_connection: data.concept_connection,
      };
      setMessages(prev => [...prev, tutorMsg]);
      setImageText('');
      setShowImageInput(false);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'tutor', content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleReExplain = async (style, sid) => {
    setLoading(true);
    try {
      const data = await api.explainAgain(style, sid || sessionId);
      const reMsg = {
        role: 'tutor',
        content: data.explanation,
        isReExplain: true,
        style: data.style_used || style,
        key_takeaway: data.key_takeaway,
        check_understanding: data.check_understanding,
      };
      setMessages(prev => [...prev, reMsg]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'tutor', content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setSessionId(null);
    setCurrentTopic(null);
    setInput('');
    setImageText('');
  };

  return (
    <div className="flex flex-col h-[calc(100vh-57px)] lg:h-screen">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <button onClick={() => navigate('/')} className="text-gray-400 hover:text-gray-600 flex-shrink-0">
          <ArrowLeft size={20} />
        </button>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-gray-900 truncate">Ask Anything</h2>
          <p className="text-xs text-gray-500 truncate">
            {currentTopic ? `Topic: ${currentTopic}` : 'Paste your problem or type your doubt'}
          </p>
        </div>
        <div className="ml-auto flex-shrink-0">
          <button onClick={handleNewChat}
            className="btn-secondary text-sm flex items-center gap-1.5 py-2 px-3">
            <RefreshCw size={16} /> New
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 space-y-4 bg-gray-50">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 bg-brand-100 rounded-2xl flex items-center justify-center mb-4">
              <span className="text-3xl">💬</span>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-1">Ask me anything</h3>
            <p className="text-sm text-gray-500 max-w-sm">
              Paste a homework problem, type your doubt, or describe what you're stuck on.
              I'll guide you step by step — no answer dumps.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <AskMessage key={i} msg={msg} sessionId={sessionId} onReExplain={handleReExplain} />
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white rounded-2xl px-5 py-4 shadow-sm border border-gray-100">
              <div className="flex items-center gap-2 text-gray-400">
                <div className="animate-spin h-4 w-4 border-2 border-brand-500 border-t-transparent rounded-full" />
                <span className="text-sm">Thinking...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Image text input + OCR status */}
      {showImageInput && (
        <div className="bg-yellow-50 border-t border-yellow-200 px-4 sm:px-6 py-3">
          <div className="flex items-start gap-2 max-w-3xl mx-auto">
            <div className="flex-1">
              {ocrBusy && (
                <p className="text-xs text-yellow-800 mb-1 flex items-center gap-2">
                  <span className="animate-spin h-3 w-3 border-2 border-yellow-500 border-t-transparent rounded-full" />
                  Extracting text… {ocrProgress}%
                </p>
              )}
              {ocrError && <p className="text-xs text-red-600 mb-1">{ocrError}</p>}
              <textarea
                className="input-field w-full text-sm"
                rows={3}
                placeholder="Extracted text appears here — confirm or edit before asking, or paste manually..."
                value={imageText}
                onChange={e => setImageText(e.target.value)}
              />
            </div>
            <button onClick={() => { setShowImageInput(false); setImageText(''); setOcrError(''); }}
              className="text-gray-400 hover:text-gray-600 mt-1">
              <X size={18} />
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="bg-white border-t border-gray-200 px-6 py-4">
        <div className="flex gap-3 max-w-3xl mx-auto">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={handleImageUpload}
          />
          <button type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={ocrBusy}
            className={`px-3 py-2 rounded-xl transition-colors disabled:opacity-50 ${
              showImageInput || imageText ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
            title="Upload / photograph a problem (OCR)"
          >
            <Camera size={18} />
          </button>
          <input
            className="input-field flex-1"
            placeholder="Type your question or paste a problem..."
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={loading}
            autoFocus
          />
          <button type="submit" className="btn-primary flex items-center gap-2" disabled={!input.trim() || loading}>
            <Send size={18} /> Ask
          </button>
        </div>
      </form>
    </div>
  );
}
