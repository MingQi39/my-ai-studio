import type { StudioChatMessage } from '@/hooks/studioChat/types';
import type { MessageResponse as ApiMessageResponse } from '@/services/api';
import { buildToolStateFromExecutions } from '@/hooks/studioChat/mapToolExecutions';

function resolveAssistantIsComplete(msg: ApiMessageResponse): boolean {
  if (msg.role !== 'assistant') return true;
  if (msg.is_complete === false) return false;

  const hasContent = Boolean(msg.content?.trim()) || Boolean(msg.thinking_content?.trim());
  const hasRunningTools = msg.tool_executions?.some(
    (ex) => ex.status === 'running' || ex.status === 'pending',
  );
  if (hasRunningTools) return false;
  if (!hasContent) return false;

  return msg.is_complete ?? true;
}

export function mapApiMessagesToStudio(apiMessages: ApiMessageResponse[]): StudioChatMessage[] {
  return apiMessages
    .map((msg) => {
      const toolState =
        msg.role === 'assistant' ? buildToolStateFromExecutions(msg.tool_executions) : {};

      return {
        id: msg.id,
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
        thinking: msg.thinking_content || undefined,
        isThinking: false,
        isComplete: resolveAssistantIsComplete(msg),
        ...toolState,
        images:
          msg.attachments && msg.attachments.length > 0
            ? msg.attachments.map((att) => ({
                id: att.id,
                url: att.url,
                name: att.name,
              }))
            : undefined,
      };
    })
    .reverse();
}

export function getLastMessageFingerprint(messages: StudioChatMessage[]): string {
  const last = messages[messages.length - 1];
  if (!last) return '';
  const toolSig = (last.toolRuns ?? [])
    .map((run) => `${run.tool_name}:${run.status}:${run.tool_output?.length ?? 0}`)
    .join('|');
  return `${last.id}:${last.content.length}:${last.thinking?.length ?? 0}:${last.isComplete === false ? '0' : '1'}:${toolSig}`;
}

/** 判断是否可能仍有后台生成（用于 SSE 不可用时的 DB 轮询） */
export function looksLikeInProgressGeneration(messages: StudioChatMessage[]): boolean {
  if (messages.length === 0) return false;

  const last = messages[messages.length - 1];
  if (last.role !== 'assistant') return false;
  if (last.isComplete === false) return true;

  return Boolean(last.toolRuns?.some((run) => run.status === 'running'));
}

export function hasRecoverableAssistantProgress(message: StudioChatMessage | undefined): boolean {
  if (!message || message.role !== 'assistant') return false;

  return (
    Boolean(message.content?.trim()) ||
    Boolean(message.thinking?.trim()) ||
    Boolean(message.toolRuns?.some((run) => run.status === 'running'))
  );
}

/** 判断是否应展示流式恢复提示（生成已中断或留下空壳消息） */
export function needsStreamRecovery(messages: StudioChatMessage[]): boolean {
  if (messages.length === 0) return false;

  const last = messages[messages.length - 1];
  if (last.role === 'user') return true;
  if (last.role === 'assistant' && last.isComplete === false) return true;
  if (last.role === 'assistant' && last.toolRuns?.some((run) => run.status === 'running')) {
    return true;
  }
  if (last.role === 'assistant' && !last.content.trim() && !(last.thinking?.trim())) return true;

  return false;
}

export function clearRecoveryPrompts(messages: StudioChatMessage[]): StudioChatMessage[] {
  return messages.map((message) =>
    message.recoveryPrompt ? { ...message, recoveryPrompt: undefined } : message,
  );
}

export function markStreamRecoveryPrompt(messages: StudioChatMessage[]): StudioChatMessage[] {
  const next = clearRecoveryPrompts(messages).map((message) =>
    message.isThinking ? { ...message, isThinking: false } : message,
  );
  const lastIdx = next.length - 1;

  if (lastIdx >= 0 && next[lastIdx].role === 'assistant') {
    const updated = [...next];
    updated[lastIdx] = {
      ...updated[lastIdx],
      isThinking: false,
      recoveryPrompt: 'interrupted',
    };
    return updated;
  }

  return [
    ...next,
    {
      id: `recovery-${Date.now()}`,
      role: 'assistant',
      content: '',
      recoveryPrompt: 'interrupted',
    },
  ];
}
