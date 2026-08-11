import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import { useAuth } from './AuthContext';

const PreferencesContext = createContext(null);

const DEFAULT_PREFS = {
  language: 'en',
  reading_level: 'standard',
  font_size: 'normal',
  tts_enabled: false,
  stt_enabled: false,
};

// Minimal i18n labels — extend as needed
const LABELS = {
  en: {
    home: 'Home',
    learn: 'Learn',
    review: 'Review',
    progress: 'Progress',
    settings: 'Settings',
    language: 'Language',
    reading_level: 'Reading Level',
    font_size: 'Font Size',
    tts: 'Text-to-Speech',
    stt: 'Speech-to-Text',
    save: 'Save',
    saved: 'Saved!',
    english: 'English',
    hindi: 'हिन्दी',
    simple: 'Simple',
    standard: 'Standard',
    normal: 'Normal',
    large: 'Large',
    xl: 'Extra Large',
    logout: 'Logout',
    back: 'Back',
    send: 'Send',
    hint: 'Hint',
    new_chat: 'New Chat',
    take_quiz: 'Take Quiz',
    type_answer: 'Type your answer...',
    greeting: 'What do you want to learn?',
    pick_topic: 'Pick a topic or type your own',
    reminders: 'Reminders',
    daily_reminder: 'Daily streak reminder',
    reminder_note: 'A friendly nudge to keep your streak going. You can turn this off anytime.',
  },
  hi: {
    home: 'होम',
    learn: 'सीखें',
    review: 'दोहराएँ',
    progress: 'प्रगति',
    settings: 'सेटिंग्स',
    language: 'भाषा',
    reading_level: 'पठन स्तर',
    font_size: 'फ़ॉन्ट आकार',
    tts: 'टेक्स्ट-टू-स्पीच',
    stt: 'स्पीच-टू-टेक्स्ट',
    save: 'सहेजें',
    saved: 'सहेजा गया!',
    english: 'English',
    hindi: 'हिन्दी',
    simple: 'सरल',
    standard: 'मानक',
    normal: 'सामान्य',
    large: 'बड़ा',
    xl: 'बहुत बड़ा',
    logout: 'लॉग आउट',
    back: 'वापस',
    send: 'भेजें',
    hint: 'संकेत',
    new_chat: 'नई चैट',
    take_quiz: 'क्विज़ लें',
    type_answer: 'अपना उत्तर लिखें...',
    greeting: 'आप क्या सीखना चाहते हैं?',
    pick_topic: 'एक विषय चुनें या अपना लिखें',
    reminders: 'रिमाइंडर',
    daily_reminder: 'दैनिक स्ट्रीक रिमाइंडर',
    reminder_note: 'आपकी स्ट्रीक जारी रखने के लिए एक दोस्ताना याद दिलाना। आप इसे कभी भी बंद कर सकते हैं।',
  },
};

const DEFAULT_FLAGS = {
  voice_enabled: false,
  gamification_enabled: false,
  quests_enabled: false,
  guardian_enabled: false,
  certificates_enabled: false,
};

export function PreferencesProvider({ children }) {
  const { user } = useAuth();
  const [prefs, setPrefs] = useState(DEFAULT_PREFS);
  const [flags, setFlags] = useState(DEFAULT_FLAGS);
  const [loaded, setLoaded] = useState(false);

  // Load preferences + feature flags on login
  useEffect(() => {
    if (!user) return;
    Promise.all([
      api.getPreferences().catch(() => ({})),
      api.getFeatures().catch(() => ({})),
    ]).then(([p, f]) => {
      setPrefs({ ...DEFAULT_PREFS, ...p });
      setFlags({ ...DEFAULT_FLAGS, ...f });
    }).finally(() => setLoaded(true));
  }, [user]);

  // Apply font size to document root
  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('font-normal', 'font-large', 'font-xl');
    if (prefs.font_size === 'large') root.classList.add('font-large');
    else if (prefs.font_size === 'xl') root.classList.add('font-xl');
  }, [prefs.font_size]);

  const updatePrefs = useCallback(async (patch) => {
    const next = { ...prefs, ...patch };
    setPrefs(next);
    try {
      await api.updatePreferences(next);
    } catch {
      // revert on failure
      setPrefs(prefs);
    }
  }, [prefs]);

  const t = useCallback((key) => {
    const lang = prefs.language || 'en';
    return LABELS[lang]?.[key] || LABELS.en[key] || key;
  }, [prefs.language]);

  return (
    <PreferencesContext.Provider value={{ prefs, updatePrefs, t, loaded, flags }}>
      {children}
    </PreferencesContext.Provider>
  );
}

export function usePreferences() {
  const ctx = useContext(PreferencesContext);
  if (!ctx) throw new Error('usePreferences must be inside PreferencesProvider');
  return ctx;
}
