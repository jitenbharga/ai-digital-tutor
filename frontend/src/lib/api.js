// Production: VITE_API_URL points to User Service (Vercel Auth Gateway).
// Dev: optionally point at local docker-compose via VITE_DEV_API_URL.
const BASE = import.meta.env.VITE_DEV_API_URL || import.meta.env.VITE_API_URL || '/api';

// SEC-5: the access token is held only in memory (module scope), never in
// localStorage — so a stored-XSS payload can't read it. The refresh token is
// an httpOnly cookie the browser sends automatically (credentials: 'include').
let _accessToken = null;

export function setAccessToken(t) {
  _accessToken = t || null;
}

export function getToken() {
  return _accessToken;
}

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

// Exchange the httpOnly refresh cookie for a fresh access token.
// Single-flight: if several requests 401 at once (access-token expiry), they
// all share ONE refresh call. The backend rotates (revokes) the refresh token
// on every use, so parallel refreshes would race — a stale second request
// would trigger reuse-detection and revoke the whole session.
let _refreshPromise = null;
export function refreshAccessToken() {
  if (_refreshPromise) return _refreshPromise;
  _refreshPromise = (async () => {
    try {
      const res = await fetch(`${BASE}/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: '{}',
      });
      if (!res.ok) return null;
      const data = await res.json();
      if (data.access_token) {
        setAccessToken(data.access_token);
        return data;
      }
    } catch { /* offline / no cookie */ }
    return null;
  })().finally(() => { _refreshPromise = null; });
  return _refreshPromise;
}

// Default per-request timeout so a hung request can't leave the UI spinning
// forever. Callers can override via opts.timeoutMs (0 disables).
const DEFAULT_TIMEOUT_MS = 30000;

// Safely parse a response body: tolerate empty (204) and non-JSON responses
// instead of throwing an opaque SyntaxError.
async function parseBody(res) {
  const text = await res.text();
  if (!text) return {};
  try { return JSON.parse(text); }
  catch {
    if (text.includes('<html') || text.includes('<!DOCTYPE')) {
      return { detail: 'Server is updating or starting up. Please wait a few seconds and try again.' };
    }
    return { detail: text.slice(0, 300) };
  }
}

async function request(path, opts = {}, _retry = true) {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchOpts } = opts;
  const controller = new AbortController();
  const timer = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : null;

  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...authHeaders(), ...fetchOpts.headers },
      credentials: 'include',
      signal: controller.signal,
      ...fetchOpts,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('Request timed out. Please try again.');
    throw new Error('Network error. Check your connection and try again.');
  } finally {
    if (timer) clearTimeout(timer);
  }

  if (res.status === 401) {
    // Try one silent refresh before bouncing to /login.
    if (_retry) {
      const refreshed = await refreshAccessToken();
      if (refreshed) return request(path, opts, false);
    }
    setAccessToken(null);
    // UX (W7): preserve where the user was so login can return them, and don't
    // re-bounce if we're already on an auth screen.
    const here = window.location.pathname + window.location.search;
    if (!/^\/(login|welcome|signup)/.test(here)) {
      window.location.href = `/login?next=${encodeURIComponent(here)}`;
    }
    throw new Error('Your session expired — please sign in again.');
  }
  const data = await parseBody(res);
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

export const api = {
  // Auth
  signup: (username, password, account_type = 'student', date_of_birth = '', email = '') =>
    request('/signup', { method: 'POST', body: JSON.stringify({ username, password, account_type, date_of_birth: date_of_birth || null, email }) }),

  // W3: account recovery
  forgotPassword: (identifier) =>
    request('/forgot-password', { method: 'POST', body: JSON.stringify({ username: identifier, email: identifier }) }),
  resetPassword: (token, newPassword) =>
    request('/reset-password', { method: 'POST', body: JSON.stringify({ token, new_password: newPassword }) }),
  requestEmailVerification: () => request('/verify-email/request', { method: 'POST' }),
  verifyEmail: (token) =>
    request('/verify-email', { method: 'POST', body: JSON.stringify({ token }) }),
  // Public resend (unverified users can't log in to hit the authed endpoint).
  resendVerification: (email) =>
    request('/verify-email/resend', { method: 'POST', body: JSON.stringify({ email }) }),

  // Continue with Google — send the GIS ID token; sets the in-memory access
  // token + refresh cookie just like /login.
  googleLogin: async (credential, accountType = 'student') => {
    const res = await fetch(`${BASE}/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ credential, account_type: accountType }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Google sign-in failed');
    setAccessToken(data.access_token);
    return data;
  },

  login: async (username, password) => {
    const form = new URLSearchParams();
    form.append('username', username);
    form.append('password', password);
    const res = await fetch(`${BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      credentials: 'include',
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');
    setAccessToken(data.access_token);
    return data;
  },

  logout: () =>
    fetch(`${BASE}/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      credentials: 'include',
      body: '{}',
    }).catch(() => {}),

  // Tutor
  tutor: (student_id, current_topic) =>
    request('/tutor', { method: 'POST', body: JSON.stringify({ student_id, current_topic }) }),

  submitAnswer: (student_id, answer) =>
    request('/submit_answer', { method: 'POST', body: JSON.stringify({ student_id, answer }) }),

  hint: (student_id, question) =>
    request('/hint', { method: 'POST', body: JSON.stringify({ student_id, question }) }),

  // Read endpoints
  progress: (student_id) => request(`/progress/${student_id}`),
  knowledgeGraph: (student_id) => request(`/knowledge-graph/${student_id}`),
  review: (student_id) => request(`/review/${student_id}`),
  studyPlan: (student_id, minutes = 30) => request(`/study-plan/${student_id}?available_minutes=${minutes}`),
  challenge: (student_id, difficulty = 'medium') => request(`/challenge/${student_id}?difficulty=${difficulty}`),
  gamification: (student_id) => request(`/gamification/${student_id}`),
  myGamification: () => request('/me/gamification'),
  updateDailyGoalTargets: (targets) => request('/me/gamification/daily-goal', { method: 'PUT', body: JSON.stringify(targets) }),
  updateReminderSettings: (settings) => request('/me/gamification/reminders', { method: 'PUT', body: JSON.stringify(settings) }),
  myQuests: () => request('/me/quests'),
  completeQuest: (questId) => request(`/me/quests/${encodeURIComponent(questId)}/complete`, { method: 'POST' }),

  // Quiz
  generateQuiz: (student_id, topic, num_questions = 10, mode = 'practice', duration_minutes = 0) =>
    request(`/quiz/${student_id}?topic=${encodeURIComponent(topic)}&num_questions=${num_questions}&mode=${mode}${mode === 'exam' ? `&duration_minutes=${duration_minutes}` : ''}`, { method: 'POST' }),

  submitQuiz: (student_id, quiz_id, answers) =>
    request(`/quiz/${student_id}/submit?quiz_id=${encodeURIComponent(quiz_id)}`, {
      method: 'POST',
      body: JSON.stringify(answers),
    }),

  quizHint: (quiz_id, question_id, hint_number) =>
    request(`/quiz/${encodeURIComponent(quiz_id)}/hint`, {
      method: 'POST',
      body: JSON.stringify({ question_id, hint_number }),
    }),

  retryWrongQuiz: (quiz_id) =>
    request(`/quiz/${encodeURIComponent(quiz_id)}/retry-wrong`, { method: 'POST' }),

  askSelection: (payload) =>
    request('/ask-selection', { method: 'POST', body: JSON.stringify(payload) }),

  downloadNotebookPdf: async () => {
    const res = await fetch(`${BASE}/me/notebook/export.pdf`, { headers: { ...authHeaders() } });
    if (!res.ok) throw new Error('Export failed');
    return await res.blob();
  },

  // Guardian endpoints
  guardianChildren: () => request('/guardian/children'),
  guardianChildOverview: (student_id) => request(`/guardian/child/${student_id}/overview`),
  generateGuardianInvite: () => request('/me/guardian-invite', { method: 'POST' }),
  redeemGuardianInvite: (code) => request('/guardian/redeem-invite', { method: 'POST', body: JSON.stringify({ code }) }),

  // Onboarding
  onboardingStart: (profile) =>
    request('/onboarding/start', { method: 'POST', body: JSON.stringify(profile) }),
  onboardingAnswer: (session_id, answer) =>
    request('/onboarding/answer', { method: 'POST', body: JSON.stringify({ session_id, answer }) }),
  onboardingComplete: (session_id) =>
    request('/onboarding/complete', { method: 'POST', body: JSON.stringify({ session_id }) }),

  // Mastery Dashboard
  masteryHistory: () => request('/me/mastery-history'),

  // Certificates & Reports
  getCertificates: () => request('/me/certificates'),
  checkCertificates: () => request('/me/check-certificates', { method: 'POST' }),
  downloadReport: () => {
    const token = getToken();
    return fetch(`${BASE}/me/report`, { headers: { Authorization: `Bearer ${token}` }, credentials: 'include' });
  },
  downloadCertPdf: (certId) => {
    const token = getToken();
    return fetch(`${BASE}/me/certificates/${certId}/pdf`, { headers: { Authorization: `Bearer ${token}` }, credentials: 'include' });
  },

  // Study buddy (shared streak)
  getBuddy: () => request('/me/buddy'),
  buddyInvite: () => request('/me/buddy/invite', { method: 'POST' }),
  buddyRedeem: (code) => request('/me/buddy/redeem', { method: 'POST', body: JSON.stringify({ code }) }),
  removeBuddy: () => request('/me/buddy', { method: 'DELETE' }),

  // Profile
  getProfile: () => request('/me/profile'),
  updateProfile: (patch) => request('/me/profile', { method: 'PUT', body: JSON.stringify(patch) }),

  // Preferences
  getFeatures: () => request('/me/features'),
  getPreferences: () => request('/me/preferences'),
  updatePreferences: (prefs) => request('/me/preferences', { method: 'PUT', body: JSON.stringify(prefs) }),

  // Learning Path & Today
  getPath: () => request('/me/path'),
  setPath: (goal) => request('/me/path', { method: 'POST', body: JSON.stringify({ goal }) }),
  getToday: () => request('/me/today'),

  // N1: Ask-Anything
  ask: (question, image_text = null) =>
    request('/ask', {
      method: 'POST',
      body: JSON.stringify({ question, ...(image_text ? { image_text } : {}) }),
    }),

  // N2: Explain-Again
  explainAgain: (style, session_id = null, topic = null) =>
    request('/explain-again', {
      method: 'POST',
      body: JSON.stringify({ style, ...(session_id ? { session_id } : {}), ...(topic ? { topic } : {}) }),
    }),

  // N3: Resume
  getResume: () => request('/me/resume'),
  trackSession: (topic, question = '', mode = '') =>
    request('/me/resume/track', { method: 'POST', body: JSON.stringify({ topic, question, mode }) }),

  // Chat Persistence (legacy per-topic — kept for backward compat)
  getChatHistory: (topic) => request(`/me/chat/${encodeURIComponent(topic)}`),
  saveChatHistory: (topic, messages) =>
    request('/me/chat/save', { method: 'POST', body: JSON.stringify({ topic, messages }) }),
  clearChatHistory: (topic) =>
    request(`/me/chat/${encodeURIComponent(topic)}`, { method: 'DELETE' }),

  // Multi-session chat history (sidebar). Each chat has its own chat_id.
  listChats: (topic = null) =>
    request(`/me/chats${topic ? `?topic=${encodeURIComponent(topic)}` : ''}`),
  createChat: (topic) =>
    request('/me/chats', { method: 'POST', body: JSON.stringify({ topic }) }),
  getChat: (chatId) => request(`/me/chats/${encodeURIComponent(chatId)}`),
  saveChat: (chatId, messages, topic = '') =>
    request(`/me/chats/${encodeURIComponent(chatId)}/save`, {
      method: 'POST',
      body: JSON.stringify({ messages, topic }),
    }),
  deleteChat: (chatId) =>
    request(`/me/chats/${encodeURIComponent(chatId)}`, { method: 'DELETE' }),

  // N4: Review-Due Count
  getReviewDueCount: () => request('/me/review-due-count'),

  // N9: Quiz History
  getQuizHistory: (topic = null) =>
    request(`/me/quiz-history${topic ? `?topic=${encodeURIComponent(topic)}` : ''}`),

  // N5: Mistakes Notebook
  getMistakes: (topic = null, resolved = null) => {
    const params = new URLSearchParams();
    if (topic) params.set('topic', topic);
    if (resolved !== null) params.set('resolved', resolved);
    const qs = params.toString();
    return request(`/me/mistakes${qs ? `?${qs}` : ''}`);
  },
  resolveMistake: (mistakeId) =>
    request(`/me/mistakes/${encodeURIComponent(mistakeId)}/resolve`, { method: 'POST' }),
  explainMistake: (mistakeId, explanation) =>
    request(`/me/mistakes/${encodeURIComponent(mistakeId)}/explain`, {
      method: 'POST', body: JSON.stringify({ explanation }),
    }),

  // N10: Curriculum Map
  getSubjects: () => request('/subjects'),
  startSubject: (subject) => request(`/subjects/${encodeURIComponent(subject)}/start`, { method: 'POST' }),
  getCurriculum: (subject) => request(`/me/curriculum/${encodeURIComponent(subject)}`),
  skipNode: (subject, nodeId) =>
    request(`/me/curriculum/${encodeURIComponent(subject)}/node/${encodeURIComponent(nodeId)}/skip`, { method: 'POST' }),
  completeNode: (subject, nodeId, body = {}) =>
    request(`/me/curriculum/${encodeURIComponent(subject)}/node/${encodeURIComponent(nodeId)}/complete`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  chooseBranch: (subject, branchGroup, chosenNodeId) =>
    request(`/me/curriculum/${encodeURIComponent(subject)}/choose-branch`, {
      method: 'POST',
      body: JSON.stringify({ branch_group: branchGroup, chosen_node_id: chosenNodeId }),
    }),

  // N13: Project-Based Learning
  getProject: (subject) =>
    request(`/me/curriculum/${encodeURIComponent(subject)}/project`),
  getNodeProjectLink: (subject, nodeId) =>
    request(`/me/curriculum/${encodeURIComponent(subject)}/node/${encodeURIComponent(nodeId)}/project-link`),
  completeMilestone: (subject, milestoneId) =>
    request(`/me/curriculum/${encodeURIComponent(subject)}/project/milestone/${encodeURIComponent(milestoneId)}/complete`, { method: 'POST' }),
  submitProject: (subject, submissionType, content) =>
    request(`/me/curriculum/${encodeURIComponent(subject)}/project/submit`, {
      method: 'POST',
      body: JSON.stringify({ submission_type: submissionType, content }),
    }),

  // N7: Progress Snapshot
  getProgressSnapshot: () => request('/me/progress-snapshot'),

  // N11: References
  getNodeResources: (subject, nodeId) =>
    request(`/me/curriculum/${encodeURIComponent(subject)}/node/${encodeURIComponent(nodeId)}/resources`),

  // N12: Personal Notebook
  getNotebook: (topic = null) =>
    request(`/me/notebook${topic ? `?topic=${encodeURIComponent(topic)}` : ''}`),
  saveNote: (selectedText, topic = '', userNote = '', sourceContext = '', nodeId = '') =>
    request('/me/notebook', {
      method: 'POST',
      body: JSON.stringify({ selected_text: selectedText, topic, user_note: userNote, source_context: sourceContext, node_id: nodeId }),
    }),
  updateNote: (noteId, userNote) =>
    request(`/me/notebook/${encodeURIComponent(noteId)}`, {
      method: 'PUT',
      body: JSON.stringify({ user_note: userNote }),
    }),
  deleteNote: (noteId) =>
    request(`/me/notebook/${encodeURIComponent(noteId)}`, { method: 'DELETE' }),

  // A2: One-tap daily session
  dailySession: () => request('/me/daily-session', { method: 'POST' }),

  // A3: Learner memory
  getMemory: () => request('/me/memory'),
  addMemory: (fact, category = 'preference') =>
    request('/me/memory', { method: 'POST', body: JSON.stringify({ fact, category }) }),
  deleteMemory: (fact) =>
    request(`/me/memory?fact=${encodeURIComponent(fact)}`, { method: 'DELETE' }),

  // A4: Code practice feedback
  codeFeedback: (payload) =>
    request('/code-feedback', { method: 'POST', body: JSON.stringify(payload) }),

  // B2: Report a bad question
  reportQuestion: (payload) =>
    request('/content-report', { method: 'POST', body: JSON.stringify(payload) }),

  // B6: Guardian weekly digest
  getDigestPrefs: () => request('/guardian/digest/prefs'),
  setDigestPrefs: (payload) =>
    request('/guardian/digest/prefs', { method: 'POST', body: JSON.stringify(payload) }),
  sendDigestNow: () => request('/guardian/digest/send-now', { method: 'POST' }),

  // B4: Exam plan
  createExamPlan: (payload) =>
    request('/me/exam-plan', { method: 'POST', body: JSON.stringify(payload) }),
  getExamPlan: (subject) => request(`/me/exam-plan?subject=${encodeURIComponent(subject)}`),
  getNextExam: () => request('/me/next-exam'),
  deleteExamPlan: (subject) =>
    request(`/me/exam-plan?subject=${encodeURIComponent(subject)}`, { method: 'DELETE' }),

  // B3: Flashcards
  syncFlashcards: () => request('/me/flashcards/sync', { method: 'POST' }),
  dueFlashcards: (limit = 20) => request(`/me/flashcards/due?limit=${limit}`),
  gradeFlashcard: (cardId, rating) =>
    request(`/me/flashcards/${encodeURIComponent(cardId)}/grade`, {
      method: 'POST',
      body: JSON.stringify({ rating }),
    }),

  // S1: Materials
  getMaterials: () => request('/me/materials'),
  uploadMaterial: async (file, title = '') => {
    const token = getToken();
    const form = new FormData();
    form.append('file', file);
    const url = `${BASE}/me/materials/upload?title=${encodeURIComponent(title)}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },
  deleteMaterial: (id) => request(`/me/materials/${id}`, { method: 'DELETE' }),
  askMaterial: (id, question) =>
    request(`/me/materials/${id}/ask`, { method: 'POST', body: JSON.stringify({ question }) }),
  quizFromMaterial: (id, numQuestions = 10) =>
    request(`/me/materials/${id}/quiz`, { method: 'POST', body: JSON.stringify({ num_questions: numQuestions }) }),

  // C4: Shareable weekly progress card
  progressCard: async () => {
    const res = await fetch(`${BASE}/me/progress-card.pdf`, { headers: { ...authHeaders() } });
    if (!res.ok) throw new Error('Could not build card');
    return await res.blob();
  },

  // C3: Re-engagement notifications
  getNotifications: () => request('/me/notifications'),
  markNotificationsRead: () => request('/me/notifications/read-all', { method: 'POST' }),
  setNotificationPrefs: (prefs) =>
    request('/me/notifications/prefs', { method: 'PUT', body: JSON.stringify(prefs) }),

  // D4: 60-second recap
  recap: (topic) => request('/me/recap', { method: 'POST', body: JSON.stringify({ topic }) }),

  // D3: Exam-readiness meter
  examReadiness: (subject) => request(`/me/exam-readiness/${encodeURIComponent(subject)}`),

  // D2: Smart cheat sheet
  makeCheatsheet: (topic, refresh = false) =>
    request('/me/cheatsheet', { method: 'POST', body: JSON.stringify({ topic, refresh }) }),
  cheatsheetPdf: async (topic) => {
    const res = await fetch(`${BASE}/me/cheatsheet/${encodeURIComponent(topic)}.pdf`, { headers: { ...authHeaders() } });
    if (!res.ok) throw new Error('PDF not ready');
    return await res.blob();
  },

  // Live step-by-step solver — check ONE step (handwriting image or typed text)
  stepCheck: async ({ problem, prevSteps = [], topic = '', file = null, stepText = '' }) => {
    const form = new FormData();
    form.append('problem', problem);
    form.append('prev_steps', JSON.stringify(prevSteps));
    if (topic) form.append('topic', topic);
    if (file) form.append('image', file);
    if (stepText) form.append('step_text', stepText);
    const res = await fetch(`${BASE}/me/step-check`, {
      method: 'POST', headers: { ...authHeaders() }, credentials: 'include', body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Step check failed');
    return data;
  },

  // D1: Photo solution step-check (vision)
  solutionCheck: async (file, question = '', topic = '') => {
    const form = new FormData();
    form.append('image', file);
    if (question) form.append('question', question);
    if (topic) form.append('topic', topic);
    const res = await fetch(`${BASE}/me/solution-check`, {
      method: 'POST', headers: { ...authHeaders() }, body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Check failed');
    return data;
  },

  // C2: Weak-area-weighted full mock test
  mockTest: (subject, num_questions = 15, duration_minutes = 20) =>
    request('/me/mock-test', { method: 'POST', body: JSON.stringify({ subject, num_questions, duration_minutes }) }),

  // One-tap "Fix my weak spots" — short practice set from mistakes + low mastery + overdue
  practiceWeakSpots: (num_questions = 8) =>
    request('/me/practice/weak-spots', { method: 'POST', body: JSON.stringify({ num_questions }) }),

  // C1: Why am I stuck? — prerequisite-gap diagnosis
  diagnoseStuck: (topic, subject = null) =>
    request(`/me/diagnose/${encodeURIComponent(topic)}${subject ? `?subject=${encodeURIComponent(subject)}` : ''}`),

  // S2: Feynman
  evaluateFeynman: (topic, explanation, materialId) =>
    request('/me/feynman/evaluate', { method: 'POST', body: JSON.stringify({ topic, explanation, material_id: materialId }) }),
  getFeynmanHistory: (topic) =>
    request(`/me/feynman/history${topic ? `?topic=${encodeURIComponent(topic)}` : ''}`),

  // S3: Cheat Sheet (material-aware; distinct path from D2 makeCheatsheet)
  generateCheatsheet: (topic, materialId) =>
    request('/me/cheatsheet/smart', { method: 'POST', body: JSON.stringify({ topic, material_id: materialId }) }),
  getCheatsheet: (topic) =>
    request(`/me/cheatsheet?topic=${encodeURIComponent(topic)}`),
  // SEC: fetch the PDF as a blob with the Authorization header instead of
  // embedding the token in a query string. Returns a Blob the caller can
  // open via URL.createObjectURL.
  getCheatsheetPdf: async (topic) => {
    const slug = topic.replace(/\s+/g, '-').toLowerCase();
    const res = await fetch(`${BASE}/me/cheatsheet/${encodeURIComponent(slug)}/pdf`, {
      headers: { ...authHeaders() },
      credentials: 'include',
    });
    if (!res.ok) throw new Error('PDF not ready');
    return await res.blob();
  },

  // SSE streaming — mint a short-lived stream ticket (never the access token
  // in the URL). Consumed by useSSE().
  streamTicket: () => request('/me/stream-ticket'),
};
