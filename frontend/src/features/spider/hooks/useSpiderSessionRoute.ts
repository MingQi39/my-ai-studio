import { useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import {
  SPIDER_ACTIVE_SESSION_KEY,
  SPIDER_DRAFT_TARGET_URL_KEY,
  spiderTargetUrlStorageKey,
} from '@/features/spider/constants/session';
import { useSpiderChatStore } from '@/features/spider/stores/useSpiderChatStore';

export function useSpiderSessionRoute() {
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
        store.setMessages([]);
        const cachedTargetUrl = sessionStorage.getItem(spiderTargetUrlStorageKey(urlId)) ?? '';
        store.setTargetUrl(cachedTargetUrl);
      }
    } else {
      const storedSessionId = sessionStorage.getItem(SPIDER_ACTIVE_SESSION_KEY);
      if (storedSessionId) {
        navigate(`/spider/chat/${storedSessionId}`, { replace: true });
        queueMicrotask(() => {
          syncingFromUrlRef.current = false;
        });
        return;
      }
      if (store.currentSessionId !== null) {
        store.startNewSession();
      } else {
        const draftTargetUrl = sessionStorage.getItem(SPIDER_DRAFT_TARGET_URL_KEY) ?? '';
        if (draftTargetUrl && store.targetUrl !== draftTargetUrl) {
          store.setTargetUrl(draftTargetUrl);
        }
      }
    }

    queueMicrotask(() => {
      syncingFromUrlRef.current = false;
    });
  }, [sessionId, navigate]);

  useEffect(() => {
    if (syncingFromUrlRef.current) return;
    if (currentSessionId && currentSessionId !== sessionId) {
      navigate(`/spider/chat/${currentSessionId}`, { replace: true });
    } else if (!currentSessionId && sessionId) {
      navigate('/spider/chat', { replace: true });
    }
  }, [currentSessionId, sessionId, navigate]);

  return { currentSessionId };
}
