import { useCallback, useRef, type Dispatch, type SetStateAction } from 'react';
import { startStreamChat, type ChatRequest } from '@/services/api';
import { applyStudioChatStreamChunk } from '@/hooks/studioChat/applyStreamChunk';
import type { StudioChatMessage } from '@/hooks/studioChat/types';

export type { StudioChatMessage } from '@/hooks/studioChat/types';
export { createStudioAssistantPlaceholder } from '@/hooks/studioChat/applyStreamChunk';

interface RunStudioChatStreamOptions {
  chatRequest: ChatRequest;
  aiMsgId: string;
  setMessages: Dispatch<SetStateAction<StudioChatMessage[]>>;
  formatErrorContent: (message: string) => string;
  onError?: (error: Error) => void;
  onComplete?: () => void;
  onCancel?: () => void;
}

export function useStudioChatStream() {
  const cancelRef = useRef<(() => void) | null>(null);
  const userCancelledRef = useRef(false);

  const cancelStream = useCallback(() => {
    userCancelledRef.current = true;
    cancelRef.current?.();
    cancelRef.current = null;
  }, []);

  const runStream = useCallback(async ({
    chatRequest,
    aiMsgId,
    setMessages,
    formatErrorContent,
    onError,
    onComplete,
    onCancel,
  }: RunStudioChatStreamOptions) => {
    userCancelledRef.current = false;
    const buffers = { thinking: '', content: '' };

    const { promise, cancel } = startStreamChat(
      chatRequest,
      (chunk) => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === aiMsgId ? applyStudioChatStreamChunk(message, chunk, buffers) : message,
          ),
        );
      },
      (error) => {
        cancelRef.current = null;
        if (userCancelledRef.current) {
          return;
        }
        setMessages((prev) =>
          prev.map((message) =>
            message.id === aiMsgId
              ? { ...message, content: formatErrorContent(error.message), isThinking: false }
              : message,
          ),
        );
        onError?.(error);
      },
      () => {
        cancelRef.current = null;
        if (userCancelledRef.current) {
          return;
        }
        onComplete?.();
      },
    );

    cancelRef.current = cancel;
    await promise;

    if (userCancelledRef.current) {
      userCancelledRef.current = false;
      onCancel?.();
    }
  }, []);

  return { runStream, cancelStream };
}
