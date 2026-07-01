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
    const runningIdx = runs.findIndex((r) => r.tool_name === tr.tool_name && r.status === 'running');

    if (tr.status === 'running') {
      runs.push({ ...tr });
    } else if (runningIdx >= 0) {
      runs[runningIdx] = { ...runs[runningIdx], ...tr };
    } else {
      runs.push({ ...tr });
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
