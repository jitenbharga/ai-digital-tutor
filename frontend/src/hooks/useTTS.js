import { useCallback, useRef } from 'react';
import { usePreferences } from '../context/PreferencesContext';

/**
 * Text-to-Speech hook using Web Speech API.
 * Respects the user's tts_enabled preference and language setting.
 */
export function useTTS() {
  const { prefs, flags } = usePreferences();
  const utterRef = useRef(null);

  const speak = useCallback((text, onEnd) => {
    // P1.1: Voice hard-gated by feature flag (COPPA biometric risk)
    if (!flags.voice_enabled || !prefs.tts_enabled || !window.speechSynthesis) {
      // Not available — still fire onEnd so callers (e.g. hands-free loop) don't hang.
      if (onEnd) onEnd();
      return;
    }

    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    // B5: match TTS voice to the tutoring language (Hinglish → Hindi voice)
    const SPEECH_CODES = {
      en: 'en-IN', hi: 'hi-IN', hinglish: 'hi-IN',
      ta: 'ta-IN', te: 'te-IN', bn: 'bn-IN', mr: 'mr-IN',
      gu: 'gu-IN', kn: 'kn-IN', ml: 'ml-IN', pa: 'pa-IN',
    };
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = SPEECH_CODES[prefs.language] || 'en-US';
    utter.rate = 0.95;
    if (onEnd) {
      utter.onend = onEnd;
      utter.onerror = onEnd;
    }
    utterRef.current = utter;
    window.speechSynthesis.speak(utter);
  }, [flags.voice_enabled, prefs.tts_enabled, prefs.language]);

  const stop = useCallback(() => {
    window.speechSynthesis?.cancel();
  }, []);

  return { speak, stop, enabled: flags.voice_enabled && prefs.tts_enabled };
}
