import { useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { SPIDER_ACTIVE_SESSION_KEY } from '@/features/spider/constants/session';
import { useSpiderChatStore } from '@/features/spider/stores/useSpiderChatStore';

export function useSpiderFilesSessionRoute() {
  const { sessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const currentSessionId = useSpiderChatStore((s) => s.currentSessionId);
  const syncingFromUrlRef = useRef(false);

  useEffect(() => {
    const urlId = sessionId ?? null;
    syncingFromUrlRef.current = true;

    const store = useSpiderChatStore.getState();
    if (urlId) {
      if (store.currentSessionId !== urlId) {
        store.setCurrentSessionId(urlId);
      }
    } else {
      const storedSessionId = sessionStorage.getItem(SPIDER_ACTIVE_SESSION_KEY);
      if (storedSessionId) {
        navigate(`/spider/files/${storedSessionId}`, { replace: true });
        queueMicrotask(() => {
          syncingFromUrlRef.current = false;
        });
        return;
      }
    }

    queueMicrotask(() => {
      syncingFromUrlRef.current = false;
    });
  }, [sessionId, navigate]);

  useEffect(() => {
    if (syncingFromUrlRef.current) return;
    if (currentSessionId && currentSessionId !== sessionId) {
      navigate(`/spider/files/${currentSessionId}`, { replace: true });
    } else if (!currentSessionId && sessionId) {
      navigate('/spider/files', { replace: true });
    }
  }, [currentSessionId, sessionId, navigate]);

  return { currentSessionId };
}
