import { useState, useRef, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';
import { useSSE } from '../lib/useSSE';
import ChatMessage from '../components/ChatMessage';
import QuizView from '../components/QuizView';
import { Send, Lightbulb, RefreshCw, ArrowLeft, Zap, ClipboardList, Volume2, Mic, MicOff, MessageCircleQuestion, NotebookPen, HelpCircle, AlertTriangle, X, AudioLines, MoreVertical, BookOpen } from 'lucide-react';
import CertificateModal from '../components/CertificateModal';
import { useTTS } from '../hooks/useTTS';
import { useSTT } from '../hooks/useSTT';
import { usePreferences } from '../context/PreferencesContext';
import { useCelebration } from '../components/CelebrationManager';
import CurriculumSidePanel from '../components/CurriculumSidePanel';
import ChatHistorySidebar from '../components/ChatHistorySidebar';

// Detect when the student is asking for help/clarification ("explain", "I don't
// understand", "idk", ...) rather than attempting an answer — so we re-explain
// instead of grading it 0% "wrong". Gated on short length so real answers that
// happen to contain these words aren't misread.
function isHelpRequest(text) {
  const t = (text || '').trim().toLowerCase();
  if (!t || t.length > 80) return false;
  return /\b(explain|clarify|clarification|i\s*(do\s*n'?t|dont|don't)\s*(understand|get|know)|what\s*do\s*you\s*mean|help|confus|i'?m\s*lost|no\s*idea|idk|rephrase|simpler|didn'?t\s*(understand|get)|can\s*you\s*(explain|help|tell|clarify)|tell\s*me\s*more|elaborate|repeat)\b/.test(t);
}

export default function Tutor() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const topic = location.state?.topic || 'Algebra';
  const subject = location.state?.subject || null;
  const navChatId = location.state?.chatId || null;
  const studentId = user?.username || 'anon';

  // Use a key to force full reset when topic changes
  const [sessionKey, setSessionKey] = useState(() => Date.now());
  // Multi-session chat history: the currently-open chat + a counter to refresh
  // the sidebar list after saves / new chats / deletes.
  const [chatId, setChatId] = useState(navChatId);
  // Header actions collapsed into a standard 3-dot (kebab) overflow menu
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    if (menuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('touchstart', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, [menuOpen]);
  const [chatsRefresh, setChatsRefresh] = useState(0);
  const [messages, setMessages] = useState([]);
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [useStreaming, setUseStreaming] = useState(true);

  // Certificate modal
  const [newCert, setNewCert] = useState(null);

  // Quiz state
  const [quizMode, setQuizMode] = useState(false);
  const [quiz, setQuiz] = useState(null);
  const [quizLoading, setQuizLoading] = useState(false);

  const bottomRef = useRef(null);
  const prevTopicRef = useRef(topic);

  const { startStream, streamingText, streamMeta, isStreaming } = useSSE();
  const { speak, stop: ttsStop, enabled: ttsEnabled } = useTTS();
  const { startListening, stopListening, listening, supported: sttSupported } = useSTT();
  const { prefs, updatePrefs, flags } = usePreferences();
  const { celebrate } = useCelebration();

  // Feature #3: hands-free voice conversation mode
  const [voiceMode, setVoiceMode] = useState(false);
  const voiceModeRef = useRef(false);
  const dictBaseRef = useRef('');  // text before dictation started (live-append base)
  const lastSpokenRef = useRef('');
  const voiceReady = ttsEnabled && sttSupported; // flag + prefs opt-in satisfied

  // N8: Highlight-to-Ask state
  const [selectedText, setSelectedText] = useState('');
  const [selectionPos, setSelectionPos] = useState(null);
  const [selSource, setSelSource] = useState({ id: '', message: '' });
  // N8: scoped side-panel state
  const [askPanel, setAskPanel] = useState(null); // { selectedText, sourceId, sourceMessage, turns:[], input:'', loading:false }
  const chatAreaRef = useRef(null);

  const scrollToBottom = () => bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  useEffect(() => { scrollToBottom(); }, [messages, streamingText, quizMode]);

  // N8: Listen for text selection in chat area
  useEffect(() => {
    const handleSelection = () => {
      const sel = window.getSelection();
      const text = sel?.toString()?.trim();
      if (text && text.length > 3 && chatAreaRef.current?.contains(sel.anchorNode)) {
        const range = sel.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        // Capture the surrounding tutor message for scoped context
        let el = sel.anchorNode;
        if (el && el.nodeType === 3) el = el.parentElement;
        const container = el?.closest?.('[data-tutor-msg]');
        setSelSource({
          id: container?.getAttribute('data-msg-id') || `sel-${Date.now()}`,
          message: container?.innerText?.slice(0, 4000) || text,
        });
        setSelectedText(text);
        setSelectionPos({ x: rect.left + rect.width / 2, y: rect.top - 10 });
      } else {
        setSelectedText('');
        setSelectionPos(null);
      }
    };
    document.addEventListener('mouseup', handleSelection);
    document.addEventListener('touchend', handleSelection);
    return () => {
      document.removeEventListener('mouseup', handleSelection);
      document.removeEventListener('touchend', handleSelection);
    };
  }, []);

  // N3: Track session on mount + topic change
  useEffect(() => {
    api.trackSession(topic).catch(() => {});
  }, [topic, sessionKey]);

  // N8: open the scoped side panel for the current selection
  const openAskPanel = () => {
    setAskPanel({
      selectedText,
      sourceId: selSource.id,
      sourceMessage: selSource.message,
      turns: [],
      input: '',
      loading: true,
    });
    setSelectedText('');
    setSelectionPos(null);
    // Fire the first question automatically ("explain this part")
    sendAskSelection('Can you explain this part?', {
      selectedText, sourceId: selSource.id, sourceMessage: selSource.message, turns: [],
    });
  };

  // N8: send a turn to /ask-selection, scoped to the highlighted span
  const sendAskSelection = async (question, ctx) => {
    const base = ctx || askPanel;
    if (!base) return;
    const q = (question || '').trim();
    if (!q) return;
    setAskPanel(p => ({
      ...(p || base),
      turns: [...(p?.turns || base.turns || []), { role: 'student', content: q }],
      input: '',
      loading: true,
    }));
    try {
      const res = await api.askSelection({
        selected_text: base.selectedText,
        source_message_id: base.sourceId,
        source_message: base.sourceMessage,
        question: q,
        topic,
      });
      setAskPanel(p => ({
        ...p,
        turns: [...p.turns, { role: 'tutor', content: res.response, probing: res.probing_question }],
        loading: false,
      }));
    } catch (err) {
      setAskPanel(p => ({
        ...p,
        turns: [...p.turns, { role: 'tutor', content: `Error: ${err.message}` }],
        loading: false,
      }));
    }
  };

  // Fetch question via regular POST
  const fetchQuestion = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.tutor(studentId, topic);
      const tutorMsg = {
        role: 'tutor',
        content: data.question || 'Let me think of a question for you...',
        mode: data.mode,
        explanation: data.explanation,
      };
      setMessages(prev => [...prev, tutorMsg]);
      setCurrentQuestion(data.question);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'tutor', content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  }, [studentId, topic]);

  // Fetch question via SSE stream
  const fetchQuestionStream = useCallback(() => {
    setLoading(true);
    startStream(studentId, topic, () => {
      setLoading(false);
    });
  }, [studentId, topic, startStream]);

  // When stream finishes, commit the streamed message
  useEffect(() => {
    if (!isStreaming && streamMeta && streamingText) {
      setMessages(prev => [...prev, {
        role: 'tutor',
        content: streamingText,
        mode: streamMeta.mode,
        explanation: streamMeta.explanation || null,
      }]);
      setCurrentQuestion(streamMeta.question || streamingText);
    }
  }, [isStreaming, streamMeta, streamingText]);

  // Track whether we loaded from saved chat (skip auto-fetch if yes)
  const loadedFromSave = useRef(false);

  // Resolve which chat to open, then load it (resume) or start fresh.
  // - If navigated with a chatId → open that chat.
  // - Else resume the most recent chat for this topic.
  // - Else create a brand-new chat and start fresh.
  useEffect(() => {
    let cancelled = false;
    setQuizMode(false);
    setQuiz(null);
    setCurrentQuestion(null);
    setAnswer('');
    loadedFromSave.current = false;

    const startFresh = () => {
      if (cancelled) return;
      setMessages([{
        role: 'tutor',
        content: `Let's study **${topic}** together! I'll adapt to your level as we go.`,
        mode: null,
      }]);
      if (useStreaming) fetchQuestionStream();
      else fetchQuestion();
    };

    const init = async () => {
      let id = navChatId;

      // No explicit chat → resume newest chat for this topic, else create one.
      if (!id) {
        try {
          const res = await api.listChats(topic);
          id = (res.chats || [])[0]?.chat_id || null;
        } catch { /* offline */ }
        if (!id) {
          try { id = (await api.createChat(topic)).chat_id; } catch { id = null; }
        }
      }
      if (cancelled) return;
      setChatId(id);

      // Load the chat's messages (resume where it ended).
      if (id) {
        try {
          const chat = await api.getChat(id);
          if (cancelled) return;
          if (chat.messages && chat.messages.length > 0) {
            setMessages(chat.messages);
            const lastTutor = [...chat.messages].reverse().find(m => m.role === 'tutor' && m.content);
            if (lastTutor) setCurrentQuestion(lastTutor.content);
            loadedFromSave.current = true;
            setChatsRefresh(x => x + 1);
            return; // resumed — don't fetch a new question
          }
        } catch { /* fall through to fresh start */ }
      }

      // Empty chat (new) or load failed → welcome + first question.
      startFresh();
      setChatsRefresh(x => x + 1);
    };

    init();
    prevTopicRef.current = topic;
    return () => { cancelled = true; };
  }, [topic, navChatId, sessionKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-save chat after messages change (debounced). Saves to the current
  // chat_id so each chat session keeps its own history.
  useEffect(() => {
    if (!chatId) return;
    if (messages.length <= 1) return; // Don't save just the welcome msg
    const timer = setTimeout(() => {
      // Strip non-serializable fields, keep only what we need
      const toSave = messages.map(m => ({
        role: m.role,
        content: m.content || '',
        mode: m.mode || null,
        ...(m.feedback ? { feedback: m.feedback } : {}),
        ...(m.hint ? { hint: m.hint } : {}),
        ...(m.reExplain ? { reExplain: m.reExplain } : {}),
      }));
      api.saveChat(chatId, toSave, topic)
        .then(() => setChatsRefresh(x => x + 1))
        .catch(() => {});
    }, 2000); // 2s debounce
    return () => clearTimeout(timer);
  }, [messages, chatId, topic]);

  // Submit answer
  // Core submit — usable from the form and from the hands-free voice loop.
  const submitText = async (raw) => {
    const text = (raw || '').trim();
    if (!text || loading) return;

    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setAnswer('');

    // A help/clarification request is NOT an answer attempt — re-explain the
    // current concept instead of grading it as wrong (0% on "can you explain me"
    // is bad UX). Keeps the current question active so they can still answer.
    if (isHelpRequest(text)) {
      await handleReExplain('simpler');
      return;
    }

    setLoading(true);
    try {
      const feedback = await api.submitAnswer(studentId, text);
      setMessages(prev => [...prev, { role: 'tutor', content: '', feedback }]);
      // Speak feedback aloud in voice mode (the next question will auto-listen).
      if (voiceModeRef.current && feedback) {
        const spoken = feedback.correct ? 'Correct! ' : 'Not quite. ';
        speak(spoken + (feedback.targeted_feedback || feedback.reasoning || ''));
      }
      if (feedback.new_certificate) {
        setNewCert(feedback.new_certificate);
      }
      // E10: Trigger celebrations (level-up, daily goal, badge)
      if (feedback.celebrations) {
        celebrate(feedback.celebrations);
      }
      setTimeout(() => {
        if (useStreaming) fetchQuestionStream();
        else fetchQuestion();
      }, 1500);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'tutor', content: `Error: ${err.message}` }]);
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    submitText(answer);
  };

  // Speak a tutor line, then (in voice mode) auto-listen and submit the reply.
  const speakThenListen = (text) => {
    if (!voiceModeRef.current || !text) return;
    speak(text, () => {
      if (!voiceModeRef.current) return;
      startListening((finalText) => {
        if (finalText && voiceModeRef.current) submitText(finalText);
      });
    });
  };

  // When a new question arrives while voice mode is on, read it out and listen.
  useEffect(() => {
    if (!voiceMode || !voiceReady || loading) return;
    if (currentQuestion && currentQuestion !== lastSpokenRef.current) {
      lastSpokenRef.current = currentQuestion;
      speakThenListen(currentQuestion);
    }
  }, [voiceMode, voiceReady, currentQuestion, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleVoiceMode = () => {
    const next = !voiceMode;
    setVoiceMode(next);
    voiceModeRef.current = next;
    if (next) {
      // Turning voice mode on = opt into TTS/STT (persisted to prefs).
      if (!prefs.tts_enabled || !prefs.stt_enabled) {
        updatePrefs({ tts_enabled: true, stt_enabled: true });
      }
      lastSpokenRef.current = ''; // let the current question be spoken now
    } else {
      ttsStop();
      stopListening();
    }
  };

  // Stop any audio when leaving the tutor page.
  useEffect(() => () => { ttsStop(); stopListening(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Request hint
  const handleHint = async () => {
    if (!currentQuestion || hintLoading) return;
    setHintLoading(true);
    try {
      const data = await api.hint(studentId, currentQuestion);
      setMessages(prev => [...prev, { role: 'tutor', content: '', hint: data.hint }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'tutor', content: `Hint error: ${err.message}` }]);
    } finally {
      setHintLoading(false);
    }
  };

  // N2: Re-explain in different style
  const handleReExplain = async (style) => {
    setLoading(true);
    try {
      const data = await api.explainAgain(style, null, topic);
      setMessages(prev => [...prev, {
        role: 'tutor',
        content: data.explanation,
        reExplain: {
          style: data.style_used || style,
          key_takeaway: data.key_takeaway,
          check_understanding: data.check_understanding,
        },
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'tutor', content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  // New Chat — creates a fresh chat session. The old chat is NOT deleted; it
  // stays in the sidebar and can be reopened to resume where it ended.
  const handleNewChat = async () => {
    try {
      const created = await api.createChat(topic);
      setChatsRefresh(x => x + 1);
      navigate('/tutor', { state: { topic, subject, chatId: created.chat_id } });
    } catch {
      // Offline fallback: just reset the view locally.
      setSessionKey(Date.now());
    }
  };

  // Resume a chat picked from the history sidebar (may switch topic too).
  const handleSelectChat = (chat) => {
    if (chat.chat_id === chatId) return;
    navigate('/tutor', {
      state: {
        topic: chat.topic || topic,
        subject: chat.topic === topic ? subject : null,
        chatId: chat.chat_id,
      },
    });
  };

  // Start in-chat quiz
  const handleStartQuiz = async () => {
    setQuizLoading(true);
    try {
      const data = await api.generateQuiz(studentId, topic, 10);
      setQuiz(data);
      setQuizMode(true);
      setMessages(prev => [...prev, {
        role: 'tutor',
        content: `Here's a 10-question quiz on **${topic}**! Answer all questions and submit to see your score.`,
        mode: 'challenge',
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'tutor', content: `Quiz error: ${err.message}` }]);
    } finally {
      setQuizLoading(false);
    }
  };

  const handleQuizSubmit = async (quizId, answers) => {
    // Do NOT exit quiz mode here — let QuizView show its results screen.
    return await api.submitQuiz(studentId, quizId, answers);
  };

  const handleQuizDone = () => {
    setQuizMode(false);
    setQuiz(null);
  };

  const handleQuizHint = (quizId, qid, n) => api.quizHint(quizId, qid, n);
  const handleRetryWrong = (quizId) => api.retryWrongQuiz(quizId);

  const handleSidePanelSelect = (topicTitle) => {
    navigate('/tutor', { state: { topic: topicTitle, subject }, replace: true });
  };

  // D4: 60-second recap
  const [recap, setRecap] = useState(null);
  const [recapLoading, setRecapLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const handleRecap = async () => {
    if (recapLoading) return;
    setRecapLoading(true);
    try { setRecap(await api.recap(topic)); }
    catch (err) { setRecap({ big_idea: `Couldn't build recap: ${err.message}`, key_points: [] }); }
    finally { setRecapLoading(false); }
  };

  // Auto-show a friendly summary of the topic/subtopic the moment it's opened, so
  // the student gets oriented before the first question. `_auto` styles the card
  // as a welcoming intro; it stays dismissible and never blocks the session.
  useEffect(() => {
    let cancelled = false;
    setRecap(null);
    setSummaryLoading(true);
    (async () => {
      try {
        const r = await api.recap(topic);
        if (!cancelled && r) setRecap({ ...r, _auto: true });
      } catch { /* summary is optional */ }
      finally { if (!cancelled) setSummaryLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [topic, sessionKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // C1: Why am I stuck? — prerequisite-gap diagnosis
  const [diagnoseLoading, setDiagnoseLoading] = useState(false);
  const [diagnosis, setDiagnosis] = useState(null);
  const handleDiagnose = async () => {
    if (diagnoseLoading) return;
    setDiagnoseLoading(true);
    try {
      setDiagnosis(await api.diagnoseStuck(topic, subject));
    } catch (err) {
      setDiagnosis({ explanation: `Couldn't diagnose: ${err.message}`, chain: [] });
    } finally {
      setDiagnoseLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-57px)] lg:h-screen overflow-hidden">
    {/* Chat history sidebar — only THIS topic's chats */}
    <ChatHistorySidebar
      topic={topic}
      currentChatId={chatId}
      refreshKey={chatsRefresh}
      onSelectChat={handleSelectChat}
      onNewChat={handleNewChat}
    />

    {/* Main tutor area */}
    <div className="flex flex-col flex-1 min-w-0 min-h-0">
      {/* Topic header */}
      <div className="flex-shrink-0 bg-white/70 dark:bg-[#0b0f18]/70 backdrop-blur-xl border-b px-4 sm:px-6 py-3 flex flex-wrap items-center gap-x-4 gap-y-2"
        style={{ borderColor: 'var(--bd)' }}>
        <button onClick={() => navigate('/learn')} className="text-ink-faint hover:text-ink-soft flex-shrink-0 cursor-pointer">
          <ArrowLeft size={20} />
        </button>
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-xl font-semibold text-ink truncate">{topic}</h2>
          <p className="text-xs text-ink-muted truncate">Adaptive AI tutoring session</p>
        </div>
        {/* All session actions collapsed into a standard 3-dot overflow menu */}
        <div className="ml-auto relative flex-shrink-0 z-50" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(o => !o)}
            className="p-2 rounded-lg text-ink-muted hover:bg-white/10 hover:text-ink-soft transition-colors cursor-pointer"
            title="Session actions" aria-label="Session actions"
            aria-haspopup="true" aria-expanded={menuOpen}
          >
            <MoreVertical size={20} />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 z-50 w-56 rounded-xl border shadow-xl py-1 animate-fade-in menu-opaque" style={{ borderColor: 'var(--bd)' }}>
              <button
                onClick={() => setUseStreaming(!useStreaming)}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-ink-soft hover:bg-white/5 transition-colors cursor-pointer"
              >
                <Zap size={16} className={useStreaming ? 'text-green-600' : 'text-ink-faint'} />
                <span className="flex-1 text-left">Streaming</span>
                <span className={`text-xs font-semibold ${useStreaming ? 'text-green-600' : 'text-ink-faint'}`}>{useStreaming ? 'On' : 'Off'}</span>
              </button>
              <button
                onClick={() => { handleStartQuiz(); setMenuOpen(false); }}
                disabled={quizLoading || quizMode}
                title={quizMode ? "Quiz in progress" : ""}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-ink-soft hover:bg-white/5 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
              >
                <ClipboardList size={16} className="text-ink-faint" />
                <span className="flex-1 text-left">{quizLoading ? 'Generating…' : quizMode ? 'Quiz in progress' : 'Take Quiz'}</span>
              </button>
              <button
                onClick={() => { handleRecap(); setMenuOpen(false); }}
                disabled={recapLoading}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-ink-soft hover:bg-white/5 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
              >
                <Zap size={16} className="text-ink-faint" />
                <span className="flex-1 text-left">{recapLoading ? 'Loading…' : '60-second Recap'}</span>
              </button>
              <button
                onClick={() => { handleDiagnose(); setMenuOpen(false); }}
                disabled={diagnoseLoading}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-ink-soft hover:bg-white/5 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
              >
                <HelpCircle size={16} className="text-ink-faint" />
                <span className="flex-1 text-left">{diagnoseLoading ? 'Checking…' : 'Why am I stuck?'}</span>
              </button>
              <div className="my-1 border-t" style={{ borderColor: 'var(--bd2)' }} />
              <button
                onClick={() => { handleNewChat(); setMenuOpen(false); }}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-ink-soft hover:bg-white/5 transition-colors cursor-pointer"
              >
                <RefreshCw size={16} className="text-ink-faint" />
                <span className="flex-1 text-left">New Chat</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Chat messages + Quiz */}
      <div ref={chatAreaRef} className="flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 py-6 space-y-4 relative">
        {/* Opening topic summary — loads automatically so the student gets oriented first */}
        {summaryLoading && !recap && (
          <div className="max-w-3xl mx-auto w-full bg-gradient-to-br from-brand-50/70 to-teal-50/40 border border-brand-200 rounded-2xl p-4 shadow-soft animate-pulse">
            <p className="flex items-center gap-2 text-brand-700 text-sm font-medium">
              <BookOpen size={16} /> Preparing a quick summary of <span className="capitalize font-semibold">{topic}</span>…
            </p>
          </div>
        )}
        {recap && (
          <div className="max-w-3xl mx-auto w-full bg-gradient-to-br from-brand-50/70 to-teal-50/40 border border-brand-200 rounded-2xl p-4 shadow-soft animate-fade-in">
            <div className="flex items-start gap-2">
              {recap._auto
                ? <BookOpen size={18} className="text-brand-600 mt-0.5 flex-shrink-0" />
                : <Zap size={18} className="text-brand-600 mt-0.5 flex-shrink-0" />}
              <div className="flex-1 min-w-0">
                <p className="font-bold text-ink text-sm">
                  {recap._auto ? 'Quick summary' : '60-second recap'}: <span className="capitalize">{topic}</span>
                </p>
                {recap._auto && <p className="text-xs text-brand-600 mt-0.5">Here's the gist before we dive in 👇</p>}
                {recap.big_idea && <p className="text-sm text-ink-soft mt-1 font-medium">{recap.big_idea}</p>}
                {recap.key_points?.length > 0 && (
                  <ul className="mt-2 space-y-1 text-sm text-ink-soft">
                    {recap.key_points.map((p, i) => <li key={i} className="flex gap-2"><span className="text-brand-400">•</span>{p}</li>)}
                  </ul>
                )}
                {recap.common_trap && (
                  <p className="text-xs text-amber-700 mt-2 bg-amber-50 rounded-lg px-2 py-1">⚠ Watch out: {recap.common_trap}</p>
                )}
              </div>
              <button onClick={() => setRecap(null)} className="text-ink-faint hover:text-ink-soft flex-shrink-0 cursor-pointer" aria-label="Dismiss summary"><X size={16} /></button>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} data-tutor-msg data-msg-id={`m-${sessionKey}-${i}`} className="max-w-3xl mx-auto w-full flex items-start gap-1 min-w-0">
            <ChatMessage message={msg} onReExplain={msg.role === 'tutor' ? handleReExplain : undefined} />
            {ttsEnabled && msg.role === 'tutor' && msg.content && (
              <button onClick={() => speak(msg.content)} className="mt-2 text-gray-300 hover:text-brand-500 transition-colors flex-shrink-0" title="Read aloud">
                <Volume2 size={16} />
              </button>
            )}
          </div>
        ))}

        {/* C1: Why-am-I-stuck diagnosis panel */}
        {diagnosis && (
          <div className="max-w-3xl mx-auto w-full border-2 border-amber-200 rounded-2xl p-4 shadow-sm"
            style={{ background: 'var(--s1)', borderColor: 'var(--bd)' }}>
            <div className="flex items-start gap-2">
              <AlertTriangle size={18} className="text-amber-500 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="font-semibold text-ink text-sm">Why am I stuck?</p>
                <p className="text-sm text-ink-soft mt-1">{diagnosis.explanation}</p>
                {diagnosis.chain?.length > 1 && (
                  <div className="mt-3 flex items-center flex-wrap gap-1.5 text-xs">
                    {diagnosis.chain.map((c, i) => (
                      <span key={i} className="flex items-center gap-1.5">
                        {i > 0 && <span className="text-ink-faint">→</span>}
                        <span className={`px-2 py-1 rounded-lg font-medium ${
                          c.is_root_gap ? 'bg-red-100 text-red-700' : 'bg-slate-50 text-ink-muted'
                        }`}>
                          {c.concept} · {Math.round(c.mastery * 100)}%
                        </span>
                      </span>
                    ))}
                  </div>
                )}
                {diagnosis.root_gap && (
                  <button
                    onClick={() => {
                      const rg = diagnosis.root_gap;
                      setDiagnosis(null);
                      navigate('/tutor', { state: { topic: rg.concept, subject }, replace: true });
                    }}
                    className="btn-primary text-xs mt-3 flex items-center gap-1.5 cursor-pointer"
                  >
                    Go fix {diagnosis.root_gap.concept} →
                  </button>
                )}
              </div>
              <button onClick={() => setDiagnosis(null)} className="text-ink-faint hover:text-ink-soft flex-shrink-0 cursor-pointer">
                <X size={16} />
              </button>
            </div>
          </div>
        )}

        {/* In-chat quiz */}
        {quizMode && quiz && (
          <div className="max-w-3xl mx-auto">
            <QuizView
              quiz={quiz}
              onSubmit={handleQuizSubmit}
              onHint={handleQuizHint}
              onRetryWrong={handleRetryWrong}
              onRetake={handleStartQuiz}
              onDone={handleQuizDone}
              compact={true}
            />
          </div>
        )}

        {/* Show streaming message in real-time */}
        {isStreaming && streamingText && (
          <ChatMessage message={{
            role: 'tutor',
            content: streamingText,
            mode: streamMeta?.mode,
            streaming: true,
          }} />
        )}

        {loading && !isStreaming && (
          <div className="flex justify-start">
            <div className="rounded-2xl px-5 py-4 shadow-sm border" style={{ background: 'var(--s1)', borderColor: 'var(--bd)' }}>
              <div className="flex items-center gap-2 text-ink-muted">
                <div className="animate-spin h-4 w-4 border-2 border-brand-500 border-t-transparent rounded-full" />
                <span className="text-sm">Thinking...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />

        {/* N8: Highlight-to-Ask + N12: Save-to-Notebook floating buttons */}
        {selectedText && selectionPos && (
          <div
            className="fixed z-50 flex gap-1.5 animate-in fade-in"
            style={{
              left: Math.min(Math.max(selectionPos.x - 80, 16), window.innerWidth - 240),
              top: Math.max(selectionPos.y - 40, 16),
            }}
          >
            <button
              onClick={openAskPanel}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-xl shadow-lg transition-all hover:-translate-y-px cursor-pointer"
              style={{ background: '#141a26', color: '#ecd9a8', boxShadow: '0 10px 26px -12px rgba(13,17,27,.6)' }}
            >
              <MessageCircleQuestion size={14} /> Ask about this
            </button>
            <button
              onClick={async () => {
                try {
                  await api.saveNote(selectedText, topic, '', '', '');
                } catch {}
                setSelectedText('');
                setSelectionPos(null);
              }}
              className="flex items-center gap-1.5 px-3 py-2 bg-teal-600 text-white text-xs font-medium rounded-xl shadow-lg hover:bg-teal-700 transition-all hover:-translate-y-px cursor-pointer"
            >
              <NotebookPen size={14} /> Save
            </button>
          </div>
        )}
      </div>

      {/* Answer input (hidden during quiz) */}
      {!quizMode && (
        <form onSubmit={handleSubmit} className="flex-shrink-0 border-t px-4 sm:px-6 py-4 bg-white/70 dark:bg-[#0b0f18]/70 backdrop-blur-xl"
          style={{ borderColor: 'var(--bd)' }}>
          <div className="flex gap-2 sm:gap-3 max-w-3xl mx-auto">
            <input
              className="input-field flex-1 min-w-0"
              placeholder="Type your answer..."
              value={answer}
              onChange={e => setAnswer(e.target.value)}
              disabled={loading}
              autoFocus
            />
            {sttSupported && (
              <button type="button"
                onClick={() => {
                  if (listening) { stopListening(); return; }
                  dictBaseRef.current = answer ? answer.trim() + ' ' : '';
                  startListening((full) => setAnswer(dictBaseRef.current + full));
                }}
                className={`px-3 py-2 rounded-xl transition-colors cursor-pointer ${listening ? 'bg-red-100 text-red-600 animate-pulse dark:bg-red-500/20 dark:text-red-300' : 'bg-gray-100 text-gray-500 hover:bg-gray-200 dark:bg-white/10 dark:text-gray-300 dark:hover:bg-white/15'}`}
                title={listening ? 'Stop dictation' : 'Dictate your answer'}
                aria-label={listening ? 'Stop dictation' : 'Dictate your answer'}
              >
                {listening ? <MicOff size={18} /> : <Mic size={18} />}
              </button>
            )}
            <button type="submit" className="btn-primary flex items-center gap-2 flex-shrink-0 cursor-pointer" disabled={!answer.trim() || loading}>
              <Send size={18} /> <span className="hidden sm:inline">Send</span>
            </button>
          </div>
        </form>
      )}

      {/* Certificate celebration modal */}
      {newCert && (
        <CertificateModal
          certificate={newCert}
          onClose={() => setNewCert(null)}
        />
      )}
    </div>

    {/* Curriculum side panel — only when subject is known */}
    {subject && (
      <CurriculumSidePanel
        subject={subject}
        currentTopic={topic}
        onSelectTopic={handleSidePanelSelect}
      />
    )}

    {/* N8: Highlight-to-ask scoped side panel (bottom sheet on mobile) */}
    {askPanel && (
      <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-96 shadow-2xl border-l border-gray-200 flex flex-col drawer-opaque"
        style={{ borderColor: 'var(--bd)' }}>
        <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--bd)' }}>
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <MessageCircleQuestion size={16} className="text-brand-600" /> Ask about selection
          </div>
          <button onClick={() => setAskPanel(null)} className="text-ink-faint hover:text-ink-soft text-lg leading-none px-2 cursor-pointer" aria-label="Close">✕</button>
        </div>
        <div className="px-4 py-2 bg-amber-50 border-b border-amber-100 text-xs text-amber-800 italic">
          “{askPanel.selectedText.slice(0, 160)}{askPanel.selectedText.length > 160 ? '…' : ''}”
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {askPanel.turns.map((t, i) => (
            <div key={i} className={t.role === 'student' ? 'text-right' : ''}>
              <div className={`inline-block px-3 py-2 rounded-2xl text-sm max-w-[85%] text-left ${
                t.role === 'student'
                  ? 'text-white'
                  : 'bg-gray-100 text-gray-800 dark:bg-white/10 dark:text-gray-100'
              }`}
                style={t.role === 'student' ? { background: 'linear-gradient(135deg,#16202f,#0f1a26 65%,#12343a)' } : undefined}>
                {t.content}
              </div>
              {t.probing && <p className="text-xs text-ink-muted mt-1 italic">{t.probing}</p>}
            </div>
          ))}
          {askPanel.loading && <p className="text-xs text-ink-faint">Thinking…</p>}
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); sendAskSelection(askPanel.input); }}
          className="p-3 border-t flex gap-2" style={{ borderColor: 'var(--bd)' }}
        >
          <input
            className="input-field flex-1 text-sm"
            placeholder="Ask a follow-up…"
            value={askPanel.input}
            onChange={(e) => setAskPanel(p => ({ ...p, input: e.target.value }))}
            disabled={askPanel.loading}
          />
          <button type="submit" className="btn-primary px-3 cursor-pointer" disabled={!askPanel.input.trim() || askPanel.loading}>
            <Send size={16} />
          </button>
        </form>
      </div>
    )}
    </div>
  );
}
