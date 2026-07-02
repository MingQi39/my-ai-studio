import {
  getLastMessageFingerprint,
  looksLikeInProgressGeneration,
  mapApiMessagesToStudio,
} from '@/hooks/studioChat/mapApiMessages';
import type { StudioChatMessage } from '@/hooks/studioChat/types';
import { getSessionMessages, getStreamStatus } from '@/services/api';

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 90;
const STABLE_ROUNDS_TO_STOP = 3;

function shouldStopDueToStability(messages: StudioChatMessage[], stableRounds: number): boolean {
  if (stableRounds < STABLE_ROUNDS_TO_STOP) return false;

  const last = messages[messages.length - 1];
  if (!last) return false;

  // 还在等待首条 assistant 或思考/正文尚未落库时，不因短暂停顿放弃
  if (last.role === 'user') return false;
  if (last.role === 'assistant' && last.isComplete === false) return false;
  if (last.role === 'assistant' && last.toolRuns?.some((run) => run.status === 'running')) {
    return false;
  }
  if (last.role === 'assistant' && !last.content.trim() && !(last.thinking?.trim())) {
    return false;
  }

  return true;
}

export type PollGenerationResult = 'completed' | 'resumed' | 'timeout' | 'cancelled';

export type PollGenerationOptions = {
  sessionId: string;
  onMessagesUpdate: (messages: StudioChatMessage[]) => void;
  isCancelled: () => boolean;
  maxAttempts?: number;
};

export async function pollGenerationFromDb({
  sessionId,
  onMessagesUpdate,
  isCancelled,
  maxAttempts = MAX_POLL_ATTEMPTS,
}: PollGenerationOptions): Promise<PollGenerationResult> {
  let stableRounds = 0;
  let lastFingerprint = '';

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (isCancelled()) return 'cancelled';

    try {
      const streamStatus = await getStreamStatus(sessionId);
      if (streamStatus.is_streaming && streamStatus.message_id) {
        return 'resumed';
      }

      const apiMessages = await getSessionMessages(sessionId, 100);
      const localMessages = mapApiMessagesToStudio(apiMessages);
      const fingerprint = getLastMessageFingerprint(localMessages);

      if (fingerprint !== lastFingerprint) {
        lastFingerprint = fingerprint;
        stableRounds = 0;
        onMessagesUpdate(localMessages);
      } else {
        stableRounds += 1;
      }

      if (!looksLikeInProgressGeneration(localMessages)) {
        return 'completed';
      }

      if (shouldStopDueToStability(localMessages, stableRounds)) {
        return 'timeout';
      }
    } catch {
      // 单次轮询失败不中断，继续尝试
    }

    if (attempt < maxAttempts - 1) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    }
  }

  return 'timeout';
}
