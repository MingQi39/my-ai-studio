import type { Message, ReActStep, ToolCall } from '@/features/travel/stores/useChatStore';
import type { SSEEvent } from '@/features/travel/types/events';

export type TravelStreamState = {
  mode: 'llm' | 'agent';
  content: string;
  thinkingSteps: ReActStep[];
  pendingToolCalls: Map<string, ToolCall>;
  hasFinalResponse: boolean;
  hasDoneEvent: boolean;
};

export type TravelStreamEffect = {
  sessionId?: string;
  message?: Partial<Pick<Message, 'content' | 'mode' | 'thinkingSteps'>>;
  done?: boolean;
  error?: string;
};

export function createTravelStreamState(mode: 'llm' | 'agent'): TravelStreamState {
  return {
    mode,
    content: '',
    thinkingSteps: [],
    pendingToolCalls: new Map(),
    hasFinalResponse: false,
    hasDoneEvent: false,
  };
}

export function reduceTravelStreamEvent(
  state: TravelStreamState,
  event: SSEEvent,
): TravelStreamEffect {
  if (event.type === 'session') {
    return { sessionId: String(event.session_id) };
  }

  if (event.type === 'start' && state.mode === 'agent') {
    return { message: { content: '🔍 正在分析并调用工具，请稍候…', mode: 'agent' } };
  }

  if (event.type === 'chunk' && event.content) {
    state.content += event.content;
    return { message: { content: state.content, mode: state.mode } };
  }

  if (event.type === 'tool_call_start') {
    state.pendingToolCalls.set(event.call_id, {
      id: event.call_id,
      tool_name: event.tool_name,
      tool_args: event.tool_args,
      status: 'pending',
    });
    return {};
  }

  if (event.type === 'tool_call_result') {
    const toolCall = state.pendingToolCalls.get(event.call_id);
    if (toolCall) {
      toolCall.result = event.result;
      toolCall.status = event.status;
      toolCall.duration_ms = event.duration_ms;
      toolCall.error = event.error;
    }
    return {};
  }

  if (event.type === 'step' && event.content) {
    const step: ReActStep = {
      type: event.step_type,
      content: event.content,
      round: event.round || 0,
      sequence: event.sequence || 0,
    };
    if (event.step_type === 'Act') {
      const completed = Array.from(state.pendingToolCalls.values()).filter(
        (toolCall) => toolCall.status !== 'pending',
      );
      if (completed.length > 0) step.toolCalls = completed;
      state.pendingToolCalls.clear();
    }
    state.thinkingSteps.push(step);
    return {
      message: {
        content: '💭 正在推理中…',
        mode: 'agent',
        thinkingSteps: [...state.thinkingSteps],
      },
    };
  }

  if (event.type === 'final_response' && event.content) {
    state.content = event.content;
    state.hasFinalResponse = true;
    return {
      message: {
        content: '✍️ 正在整理最终回复…',
        mode: state.mode,
        thinkingSteps: [...state.thinkingSteps],
      },
    };
  }

  if (event.type === 'done') {
    state.hasDoneEvent = true;
    if (
      state.mode === 'agent'
      && !state.hasFinalResponse
      && !state.content
      && state.thinkingSteps.length > 0
    ) {
      const lastThink = [...state.thinkingSteps].reverse().find((step) => step.type === 'Think');
      if (lastThink) state.content = lastThink.content;
    }
    return {
      message: {
        content:
          state.content
          || (state.mode === 'agent' ? '已完成推理，但未生成最终回复。' : '无回复内容'),
        mode: state.mode,
        thinkingSteps: state.mode === 'agent' ? [...state.thinkingSteps] : undefined,
      },
      done: true,
    };
  }

  if (event.type === 'error') {
    state.pendingToolCalls.clear();
    return { error: event.message };
  }

  return {};
}
