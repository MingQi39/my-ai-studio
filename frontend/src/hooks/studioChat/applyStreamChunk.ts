import type { ChatStreamChunk } from '@/services/api';
import type { StudioChatMessage, StudioChatStreamBuffers } from '@/hooks/studioChat/types';

export function createStudioAssistantPlaceholder(id?: string): StudioChatMessage {
  return {
    id: id ?? `${Date.now() + 1}`,
    role: 'assistant',
    content: '',
    isThinking: true,
    thinking: '',
  };
}

export function applyStudioChatStreamChunk(
  message: StudioChatMessage,
  chunk: ChatStreamChunk,
  buffers: StudioChatStreamBuffers,
): StudioChatMessage {
  if (chunk.type === 'thinking') {
    buffers.thinking += chunk.thinking || '';
    return { ...message, thinking: buffers.thinking, isThinking: true };
  }

  if (chunk.type === 'content') {
    buffers.content += chunk.content || '';
    return { ...message, content: buffers.content, isThinking: true };
  }

  if (chunk.type === 'tool_result' && chunk.tool_result) {
    const tr = chunk.tool_result;
    const runs = [...(message.toolRuns || [])];
    const callId = typeof tr.call_id === 'string' ? tr.call_id : undefined;
    const runningIdx = callId
      ? runs.findIndex((r) => r.call_id === callId)
      : runs.findIndex((r) => r.tool_name === tr.tool_name && r.status === 'running');

    if (tr.status === 'running') {
      runs.push({
        call_id: callId,
        tool_name: tr.tool_name,
        tool_type: tr.tool_type,
        tool_input: tr.tool_input,
        status: 'running',
      });
    } else if (runningIdx >= 0) {
      runs[runningIdx] = {
        ...runs[runningIdx],
        ...tr,
        call_id: callId ?? runs[runningIdx].call_id,
      };
    } else {
      runs.push({
        call_id: callId,
        ...tr,
      });
    }

    let tool = message.tool;
    if (tr.tool_name === 'execute_python') {
      const code = String(tr.tool_input?.code ?? '');
      if (tr.status === 'running') {
        tool = { name: tr.tool_name, code, status: 'running' };
      } else {
        tool = {
          name: tr.tool_name,
          code,
          output: tr.tool_output,
          status: tr.status === 'error' ? 'running' : 'completed',
        };
      }
    }

    return { ...message, toolRuns: runs, tool, isThinking: true };
  }

  if (chunk.type === 'done') {
    return { ...message, isThinking: false };
  }

  return message;
}
