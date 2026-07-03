/**
 * 对比对话 Hook — /api/v1/travel/compare
 * 并排流式接收 LLM（chunk）与 Agent（step/final_response）两路 SSE。
 */

import { useRef } from 'react';
import { toast } from 'sonner';
import {
  useChatStore,
  type ReActStep,
  type ToolCall,
} from '@/features/travel/stores/useChatStore';
import { SSEClient } from '@/features/travel/services/sse/SSEClient';
import type { SSEEvent } from '@/features/travel/types/events';
import { TRAVEL_API_BASE, travelHeaders } from '@/features/travel/services/api/client';
import { useTravelRuntime } from '@/features/travel/TravelRuntimeContext';

type CompareSource = 'llm' | 'agent';

interface SourceState {
  messageId: string;
  contentBuffer: string;
  thinkingSteps: ReActStep[];
  pendingToolCalls: Map<string, ToolCall>;
  hasFinalResponse: boolean;
  hasDoneEvent: boolean;
  failed: boolean;
}

function createSourceState(source: CompareSource, messageId: string): SourceState {
  return {
    messageId,
    contentBuffer: '',
    thinkingSteps: [],
    pendingToolCalls: new Map(),
    hasFinalResponse: false,
    hasDoneEvent: false,
    failed: false,
  };
}

export function useCompare() {
  const { modelConfigId } = useTravelRuntime();
  const clientRef = useRef<SSEClient | null>(null);

  const sendMessage = async (text: string) => {
    if (!modelConfigId) {
      throw new Error('请先在设置中配置模型连接');
    }

    const { addMessage, updateMessage, setGenerating, setCurrentSessionId, bumpSessionList } =
      useChatStore.getState();
    const ts = Date.now();

    addMessage({
      id: `user-${ts}`,
      role: 'user',
      content: text,
      timestamp: ts,
    });

    const llmMessageId = `llm-${ts}`;
    const agentMessageId = `agent-${ts}`;

    addMessage({
      id: llmMessageId,
      role: 'assistant',
      content: '🔄 原生 LLM 正在思考…',
      mode: 'llm',
      timestamp: ts + 1,
    });

    addMessage({
      id: agentMessageId,
      role: 'assistant',
      content: '🔄 ReAct Agent 正在连接…',
      mode: 'agent',
      thinkingSteps: [],
      timestamp: ts + 2,
    });

    setGenerating(true);

    const states: Record<CompareSource, SourceState> = {
      llm: createSourceState('llm', llmMessageId),
      agent: createSourceState('agent', agentMessageId),
    };

    const updateSource = (
      source: CompareSource,
      updates: Partial<{ content: string; thinkingSteps: ReActStep[] }>,
    ) => {
      updateMessage(states[source].messageId, updates);
    };

    const failSource = (source: CompareSource, message: string) => {
      const state = states[source];
      if (state.failed) return;
      state.failed = true;
      state.hasDoneEvent = true;
      updateSource(source, { content: `❌ ${message}` });
      toast.error(`${source === 'llm' ? '原生 LLM' : 'ReAct Agent'}：${message}`);
    };

    const maybeFinish = () => {
      const llmDone = states.llm.hasDoneEvent || states.llm.failed;
      const agentDone = states.agent.hasDoneEvent || states.agent.failed;
      if (llmDone && agentDone) {
        setGenerating(false);
      }
    };

    const handleAgentEvent = (source: CompareSource, event: SSEEvent) => {
      const state = states[source];

      if (event.type === 'start') {
        updateSource(source, { content: '🔍 正在分析并调用工具…' });
        return;
      }

      if (event.type === 'step' && 'step_type' in event && event.content) {
        if (event.step_type === 'Act') {
          const completedToolCalls = Array.from(state.pendingToolCalls.values()).filter(
            (tc) => tc.status !== 'pending',
          );
          state.thinkingSteps.push({
            type: event.step_type,
            content: event.content,
            round: event.round || 0,
            sequence: event.sequence || 0,
            toolCalls: completedToolCalls,
          });
          state.pendingToolCalls.clear();
        } else {
          state.thinkingSteps.push({
            type: event.step_type,
            content: event.content,
            round: event.round || 0,
            sequence: event.sequence || 0,
          });
        }
        updateSource(source, {
          content: '💭 正在推理中…',
          thinkingSteps: [...state.thinkingSteps],
        });
        return;
      }

      if (event.type === 'tool_call_start' && 'call_id' in event) {
        state.pendingToolCalls.set(event.call_id, {
          id: event.call_id,
          tool_name: event.tool_name,
          tool_args: event.tool_args,
          status: 'pending',
        });
        return;
      }

      if (event.type === 'tool_call_result' && 'call_id' in event) {
        const toolCall = state.pendingToolCalls.get(event.call_id);
        if (toolCall) {
          toolCall.result = event.result;
          toolCall.status = event.status;
          toolCall.duration_ms = event.duration_ms;
          toolCall.error = event.error;
        }
        return;
      }

      if (event.type === 'final_response' && 'content' in event && event.content) {
        state.contentBuffer = event.content;
        state.hasFinalResponse = true;
        updateSource(source, {
          content: '✍️ 正在整理最终回复…',
          thinkingSteps: [...state.thinkingSteps],
        });
        return;
      }

      if (event.type === 'done') {
        state.hasDoneEvent = true;
        if (!state.hasFinalResponse && !state.contentBuffer && state.thinkingSteps.length > 0) {
          const lastThink = state.thinkingSteps.filter((s) => s.type === 'Think').pop();
          if (lastThink) state.contentBuffer = lastThink.content;
        }
        updateSource(source, {
          content: state.contentBuffer || '已完成推理，但未生成最终回复。',
          thinkingSteps: [...state.thinkingSteps],
        });
        maybeFinish();
        return;
      }

      if (event.type === 'error' && 'message' in event) {
        failSource(source, event.message);
        maybeFinish();
      }
    };

    const handleLlmEvent = (source: CompareSource, event: SSEEvent) => {
      const state = states[source];

      if (event.type === 'chunk' && 'content' in event && event.content) {
        state.contentBuffer += event.content;
        updateSource(source, { content: state.contentBuffer });
        return;
      }

      if (event.type === 'done') {
        state.hasDoneEvent = true;
        updateSource(source, {
          content: state.contentBuffer || '无回复内容',
        });
        maybeFinish();
        return;
      }

      if (event.type === 'error' && 'message' in event) {
        failSource(source, event.message);
        maybeFinish();
      }
    };

    const sessionIdForRequest = useChatStore.getState().currentSessionId;

    const client = new SSEClient({
      url: `${TRAVEL_API_BASE}/travel/compare`,
      method: 'POST',
      headers: travelHeaders(),
      body: JSON.stringify({
        message: text,
        session_id: sessionIdForRequest,
        max_rounds: 3,
        model_config_id: modelConfigId,
      }),
      onEvent: (event: SSEEvent) => {
        if (event.type === 'session' && 'session_id' in event) {
          setCurrentSessionId(String(event.session_id));
          bumpSessionList();
          return;
        }
        const source = (event.source || 'llm') as CompareSource;
        if (source === 'agent') {
          handleAgentEvent(source, event);
        } else {
          handleLlmEvent(source, event);
        }
      },
      onError: (error) => {
        const message = error.message || '对比请求失败';
        if (!states.llm.hasDoneEvent) failSource('llm', message);
        if (!states.agent.hasDoneEvent) failSource('agent', message);
        setGenerating(false);
      },
      onComplete: () => {
        if (!states.llm.hasDoneEvent && !states.llm.failed) {
          failSource('llm', '连接中断，未收到完整回复');
        }
        if (!states.agent.hasDoneEvent && !states.agent.failed) {
          failSource('agent', '连接中断，未收到完整回复');
        }
        if (useChatStore.getState().isGenerating) {
          useChatStore.getState().setGenerating(false);
        }
      },
    });

    clientRef.current = client;
    await client.start();
    clientRef.current = null;
  };

  return { sendMessage };
};
