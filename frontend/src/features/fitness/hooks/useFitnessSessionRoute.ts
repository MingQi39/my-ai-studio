import { useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { useFitnessChatStore } from '@/features/fitness/stores/useFitnessChatStore';

export function useFitnessSessionRoute() {
  const { sessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const currentSessionId = useFitnessChatStore((s) => s.currentSessionId);
  const syncingFromUrlRef = useRef(false);

  // URL -> Store
  useEffect(() => {
    const urlId = sessionId ?? null;
    syncingFromUrlRef.current = true;

    const store = useFitnessChatStore.getState();
    if (urlId) {
      if (store.currentSessionId !== urlId) {
        store.setCurrentSessionId(urlId);
        store.setMessages([]);
      }
    } else if (store.currentSessionId !== null) {
      store.startNewSession();
    }

    queueMicrotask(() => {
      syncingFromUrlRef.current = false;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Store -> URL
  useEffect(() => {
    if (syncingFromUrlRef.current) return;
    if (currentSessionId && currentSessionId !== sessionId) {
      navigate(`/fitness/chat/${currentSessionId}`, { replace: true });
    } else if (!currentSessionId && sessionId) {
      navigate('/fitness/chat', { replace: true });
    }
  }, [currentSessionId, sessionId, navigate]);

  return { currentSessionId };
}

