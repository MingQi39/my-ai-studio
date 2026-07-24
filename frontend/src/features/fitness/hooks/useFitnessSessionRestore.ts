import { useEffect, useRef } from 'react';

import { loadFitnessSession } from '@/features/fitness/services/api/sessions';
import { useFitnessChatStore } from '@/features/fitness/stores/useFitnessChatStore';
import type { StudioChatMessage } from '@/hooks/studioChat/types';

export function useFitnessSessionRestore(
  resumeActiveGeneration: (
    sessionId: string,
    messages: StudioChatMessage[],
  ) => Promise<boolean>,
) {
  const currentSessionId = useFitnessChatStore((s) => s.currentSessionId);
  const messages = useFitnessChatStore((s) => s.messages);
  const isGenerating = useFitnessChatStore((s) => s.isGenerating);
  const isLoadingHistory = useFitnessChatStore((s) => s.isLoadingHistory);
  const sessionEpoch = useFitnessChatStore((s) => s.sessionEpoch);
  const setLoadingHistory = useFitnessChatStore((s) => s.setLoadingHistory);
  const setMessages = useFitnessChatStore((s) => s.setMessages);
  const setRecommendations = useFitnessChatStore((s) => s.setRecommendations);
  const resumeRef = useRef(resumeActiveGeneration);
  resumeRef.current = resumeActiveGeneration;

  useEffect(() => {
    if (!currentSessionId) return;
    if (messages.length > 0) return;
    if (isGenerating) return;
    if (isLoadingHistory) return;

    setLoadingHistory(true);
    void loadFitnessSession(currentSessionId)
      .then(({ messages: restored, recommendations }) => {
        if (useFitnessChatStore.getState().currentSessionId !== currentSessionId) {
          return;
        }
        setMessages(restored);
        if (recommendations.length > 0) {
          setRecommendations(recommendations);
        }
        void resumeRef.current(currentSessionId, restored).catch((error) => {
          console.error('Failed to resume fitness generation:', error);
        });
      })
      .catch((e) => {
        console.error(e);
      })
      .finally(() => setLoadingHistory(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionId, sessionEpoch]);
}
