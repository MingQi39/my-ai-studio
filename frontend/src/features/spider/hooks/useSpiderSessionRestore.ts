import { useEffect } from 'react';

import {
  SPIDER_DRAFT_TARGET_URL_KEY,
  SPIDER_GENERATING_SESSION_KEY,
  spiderTargetUrlStorageKey,
} from '@/features/spider/constants/session';
import { loadSpiderSession } from '@/features/spider/services/api/sessions';
import { useSpiderChatStore } from '@/features/spider/stores/useSpiderChatStore';
import { useSpiderWorkspace } from '@/features/spider/hooks/useSpiderWorkspace';
import type { StudioChatMessage } from '@/hooks/studioChat/types';

function readStoredTargetUrl(sessionId: string | null): string {
  if (sessionId) {
    return sessionStorage.getItem(spiderTargetUrlStorageKey(sessionId)) ?? '';
  }
  return sessionStorage.getItem(SPIDER_DRAFT_TARGET_URL_KEY) ?? '';
}

function markInterruptedToolRuns(messages: StudioChatMessage[]): StudioChatMessage[] {
  return messages.map((message) => {
    if (!message.toolRuns?.length) return { ...message, isThinking: false };
    return {
      ...message,
      isThinking: false,
      toolRuns: message.toolRuns.map((run) =>
        run.status === 'running'
          ? {
              ...run,
              status: 'error' as const,
              tool_output: run.tool_output || '页面已刷新，实时执行状态已中断',
            }
          : run,
      ),
    };
  });
}

export function useSpiderSessionRestore() {
  const currentSessionId = useSpiderChatStore((s) => s.currentSessionId);
  const messages = useSpiderChatStore((s) => s.messages);
  const isLoadingHistory = useSpiderChatStore((s) => s.isLoadingHistory);
  const sessionEpoch = useSpiderChatStore((s) => s.sessionEpoch);
  const restoreInterruptedHint = useSpiderChatStore((s) => s.restoreInterruptedHint);
  const setLoadingHistory = useSpiderChatStore((s) => s.setLoadingHistory);
  const setMessages = useSpiderChatStore((s) => s.setMessages);
  const setTargetUrl = useSpiderChatStore((s) => s.setTargetUrl);
  const setRestoreInterruptedHint = useSpiderChatStore((s) => s.setRestoreInterruptedHint);
  const { refreshWorkspace } = useSpiderWorkspace();

  useEffect(() => {
    if (!currentSessionId) return;
    if (messages.length > 0) return;
    if (isLoadingHistory) return;

    setLoadingHistory(true);
    void loadSpiderSession(currentSessionId)
      .then(({ messages: restored, targetUrl }) => {
        // Another session switch may have completed while this request was in flight.
        if (useSpiderChatStore.getState().currentSessionId !== currentSessionId) {
          return;
        }
        // In-memory live stream may have hydrated this session while the request was pending.
        if (useSpiderChatStore.getState().messages.length > 0) {
          return;
        }

        const wasGenerating =
          sessionStorage.getItem(SPIDER_GENERATING_SESSION_KEY) === currentSessionId;
        const hasIncomplete = restored.some(
          (message) => message.role === 'assistant' && message.isComplete === false,
        );
        const interrupted = wasGenerating || hasIncomplete;

        if (wasGenerating) {
          sessionStorage.removeItem(SPIDER_GENERATING_SESSION_KEY);
        }

        if (interrupted) {
          setRestoreInterruptedHint(true);
          setMessages(markInterruptedToolRuns(restored));
        } else {
          setRestoreInterruptedHint(false);
          setMessages(restored);
        }
        setTargetUrl(targetUrl ?? readStoredTargetUrl(currentSessionId));
        void refreshWorkspace();
      })
      .catch((error) => console.error(error))
      .finally(() => {
        if (useSpiderChatStore.getState().currentSessionId === currentSessionId) {
          setLoadingHistory(false);
        }
      });
  }, [
    currentSessionId,
    sessionEpoch,
    isLoadingHistory,
    messages.length,
    setLoadingHistory,
    setMessages,
    setTargetUrl,
    setRestoreInterruptedHint,
    refreshWorkspace,
  ]);

  // After an interrupted refresh, keep workspace list warm for a short while —
  // the backend pipeline may still finish writing files.
  useEffect(() => {
    if (!restoreInterruptedHint || !currentSessionId) return;

    void refreshWorkspace();
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      if (Date.now() - startedAt > 30000) {
        window.clearInterval(timer);
        return;
      }
      void refreshWorkspace();
    }, 3000);

    return () => window.clearInterval(timer);
  }, [restoreInterruptedHint, currentSessionId, refreshWorkspace]);
}
