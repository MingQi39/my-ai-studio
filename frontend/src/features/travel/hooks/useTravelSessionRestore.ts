/**
 * 进入旅行对话页时，若已有 sessionId 且本地无消息，则从服务端恢复历史。
 */

import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useChatStore } from '@/features/travel/stores/useChatStore';
import { loadTravelSessionMessages } from '@/features/travel/services/api/sessions';

export function useTravelSessionRestore() {
  const currentSessionId = useChatStore((state) => state.currentSessionId);
  const messages = useChatStore((state) => state.messages);
  const sessionEpoch = useChatStore((state) => state.sessionEpoch);
  const restoredRef = useRef<string | null>(null);
  const loadingRef = useRef<string | null>(null);

  useEffect(() => {
    if (!currentSessionId) {
      restoredRef.current = null;
      return;
    }

    if (restoredRef.current !== null && restoredRef.current !== currentSessionId) {
      restoredRef.current = null;
    }

    if (messages.length > 0) {
      return;
    }

    if (restoredRef.current === currentSessionId) {
      return;
    }

    if (loadingRef.current === currentSessionId) {
      return;
    }

    const epochAtStart = sessionEpoch;
    const sessionIdAtStart = currentSessionId;
    restoredRef.current = currentSessionId;
    loadingRef.current = currentSessionId;

    const { setLoadingHistory, setMessages } = useChatStore.getState();
    setLoadingHistory(true);

    loadTravelSessionMessages(sessionIdAtStart)
      .then((loaded) => {
        const state = useChatStore.getState();
        if (state.sessionEpoch !== epochAtStart) return;
        if (state.currentSessionId !== sessionIdAtStart) return;
        setMessages(loaded);
      })
      .catch((error) => {
        console.error('Failed to restore travel session:', error);
        toast.error('加载对话历史失败');
        if (restoredRef.current === sessionIdAtStart) {
          restoredRef.current = null;
        }
      })
      .finally(() => {
        if (loadingRef.current === sessionIdAtStart) {
          loadingRef.current = null;
        }
        const state = useChatStore.getState();
        if (state.sessionEpoch === epochAtStart && state.currentSessionId === sessionIdAtStart) {
          setLoadingHistory(false);
        }
      });
  }, [currentSessionId, messages.length, sessionEpoch]);
}
