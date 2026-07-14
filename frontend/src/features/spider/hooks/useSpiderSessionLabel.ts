import { useEffect, useState } from 'react';

import { spiderTargetUrlStorageKey } from '@/features/spider/constants/session';
import { listSpiderSessions, loadSpiderSession } from '@/features/spider/services/api/sessions';
import { useSpiderChatStore } from '@/features/spider/stores/useSpiderChatStore';

function readStoredTargetUrl(sessionId: string): string {
  return sessionStorage.getItem(spiderTargetUrlStorageKey(sessionId))?.trim() || '';
}

/**
 * Resolves display metadata for the active spider session.
 * Uses the same session list source as the sidebar for titles.
 * Target URL is resolved from store → sessionStorage → persisted messages.
 * Files remain scoped by session_id; title/URL are display-only.
 */
export function useSpiderSessionLabel(sessionId: string | null) {
  const [title, setTitle] = useState<string | null>(null);
  const [targetUrl, setTargetUrl] = useState<string | null>(null);
  const storeTargetUrl = useSpiderChatStore((s) => s.targetUrl);
  const currentSessionId = useSpiderChatStore((s) => s.currentSessionId);
  const sessionListVersion = useSpiderChatStore((s) => s.sessionListVersion);

  useEffect(() => {
    if (!sessionId) {
      setTitle(null);
      setTargetUrl(null);
      return;
    }

    let cancelled = false;

    const fromStore =
      currentSessionId === sessionId && storeTargetUrl.trim() ? storeTargetUrl.trim() : '';
    const fromStorage = readStoredTargetUrl(sessionId);
    const immediate = fromStore || fromStorage || null;
    setTargetUrl(immediate);

    void listSpiderSessions()
      .then((sessions) => {
        if (cancelled) return;
        const match = sessions.find((session) => session.id === sessionId);
        setTitle(match?.title?.trim() || null);
      })
      .catch(() => {
        if (!cancelled) setTitle(null);
      });

    if (!immediate) {
      void loadSpiderSession(sessionId)
        .then(({ targetUrl: restored }) => {
          if (cancelled) return;
          const next = restored?.trim() || null;
          setTargetUrl(next);
          if (next && useSpiderChatStore.getState().currentSessionId === sessionId) {
            useSpiderChatStore.getState().setTargetUrl(next);
          }
        })
        .catch(() => {
          /* keep null */
        });
    }

    return () => {
      cancelled = true;
    };
  }, [sessionId, sessionListVersion, currentSessionId, storeTargetUrl]);

  return {
    title,
    targetUrl,
  };
}
