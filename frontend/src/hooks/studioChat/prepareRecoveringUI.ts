import { createStudioAssistantPlaceholder } from '@/hooks/studioChat/applyStreamChunk';
import type { StudioChatMessage } from '@/hooks/studioChat/types';
import { clearRecoveryPrompts, looksLikeInProgressGeneration } from '@/hooks/studioChat/mapApiMessages';

/** 刷新/重试恢复时，立刻在对话区展示 assistant 占位或 thinking 状态 */
export function prepareRecoveringAssistantUI(
  messages: StudioChatMessage[],
  assistantMessageId?: string | null,
): StudioChatMessage[] {
  const base = clearRecoveryPrompts(messages);
  if (!looksLikeInProgressGeneration(base)) return base;

  const last = base[base.length - 1];
  if (last.role === 'user') {
    return [...base, createStudioAssistantPlaceholder(assistantMessageId ?? undefined)];
  }

  if (last.role === 'assistant') {
    const next = [...base];
    next[next.length - 1] = {
      ...last,
      isThinking: true,
      recoveryPrompt: undefined,
    };
    return next;
  }

  return base;
}

export function clearAssistantThinkingState(messages: StudioChatMessage[]): StudioChatMessage[] {
  return messages.map((message) =>
    message.isThinking ? { ...message, isThinking: false } : message,
  );
}
