import { useState, useCallback, useRef } from 'react';
import { api } from './api';

/**
 * Hook for consuming SSE from /tutor/stream.
 * Returns { startStream, streamingText, streamMeta, isStreaming }
 */
export function useSSE() {
  const [streamingText, setStreamingText] = useState('');
  const [streamMeta, setStreamMeta] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const sourceRef = useRef(null);

  const stopStream = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const startStream = useCallback(async (studentId, topic, onDone) => {
    stopStream();
    setStreamingText('');
    setStreamMeta(null);
    setIsStreaming(true);

    // SEC: mint a short-lived, single-purpose stream ticket (Authorization
    // header) instead of putting the access token in the EventSource URL.
    let ticket;
    try {
      ({ ticket } = await api.streamTicket());
    } catch {
      setIsStreaming(false);
      return () => {};
    }
    const url = `/api/tutor/stream?current_topic=${encodeURIComponent(topic)}&ticket=${encodeURIComponent(ticket)}`;

    const es = new EventSource(url);
    sourceRef.current = es;

    es.addEventListener('meta', (e) => {
      try {
        const meta = JSON.parse(e.data);
        setStreamMeta(meta);
        // Show the question immediately
        if (meta.question) {
          setStreamingText(meta.question);
        }
      } catch {}
    });

    es.addEventListener('explanation', (e) => {
      try {
        const explanation = JSON.parse(e.data);
        setStreamMeta(prev => ({ ...prev, explanation }));
      } catch {}
    });

    es.addEventListener('token', (e) => {
      try {
        const { text } = JSON.parse(e.data);
        setStreamingText(prev => prev + text);
      } catch {}
    });

    es.addEventListener('done', (e) => {
      stopStream();
      if (onDone) onDone();
    });

    es.onerror = () => {
      stopStream();
    };

    return () => stopStream();
  }, [stopStream]);

  return { startStream, stopStream, streamingText, streamMeta, isStreaming };
}
