import type { StudioChatMessage } from '@/hooks/studioChat/types';

/**
 * The latest assistant message that can be resumed: one that was interrupted
 * mid-run (`isComplete === false`) or ended in a structured failure. Mirrors the
 * backend's `find_resumable_assistant_message`.
 */
export function findResumableMessage(
  messages: StudioChatMessage[],
): StudioChatMessage | undefined {
  return [...messages]
    .reverse()
    .find((m) => m.role === 'assistant' && (m.isComplete === false || Boolean(m.failure)));
}
