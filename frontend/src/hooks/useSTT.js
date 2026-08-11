import { useState, useCallback, useRef } from 'react';
import { usePreferences } from '../context/PreferencesContext';

/**
 * Speech-to-Text hook using Web Speech API (SpeechRecognition).
 * Respects the user's stt_enabled preference and language setting.
 */
export function useSTT() {
  const { prefs, flags } = usePreferences();
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const recogRef = useRef(null);

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  // P1.1: Voice hard-gated by feature flag (COPPA biometric risk)
  const supported = !!SpeechRecognition && flags.voice_enabled;

  const startListening = useCallback((onResult) => {
    if (!SpeechRecognition || !flags.voice_enabled) return;

    const recog = new SpeechRecognition();
    recog.lang = prefs.language === 'hi' ? 'hi-IN' : 'en-US';
    recog.interimResults = true;
    recog.maxAlternatives = 1;
    recog.continuous = true;   // Claude-style: keep dictating until user taps stop

    recog.onresult = (event) => {
      // Rebuild the FULL transcript (interim + final) from all results every
      // event, so the caller can show a live, complete transcript. Simple and
      // can't miss/duplicate — caller sets (not appends) base + this.
      let full = '';
      for (let i = 0; i < event.results.length; i++) {
        full += event.results[i][0].transcript;
      }
      console.log('[STT] result:', JSON.stringify(full));
      setTranscript(full);
      if (onResult) onResult(full);
    };

    recog.onstart = () => console.log('[STT] started (lang=%s)', recog.lang);
    recog.onspeechstart = () => console.log('[STT] speech detected');
    recog.onend = () => { console.log('[STT] ended'); setListening(false); };
    recog.onerror = (e) => {
      console.warn('[STT] error:', e.error);   // e.g. not-allowed, no-speech, network
      setListening(false);
    };

    recogRef.current = recog;
    setListening(true);
    setTranscript('');
    try {
      recog.start();
      console.log('[STT] start() called');
    } catch (err) {
      console.warn('[STT] start() threw:', err?.message || err);
      setListening(false);
    }
  }, [SpeechRecognition, prefs.stt_enabled, prefs.language]);

  const stopListening = useCallback(() => {
    recogRef.current?.stop();
    setListening(false);
  }, []);

  return { startListening, stopListening, listening, transcript, supported };
}
