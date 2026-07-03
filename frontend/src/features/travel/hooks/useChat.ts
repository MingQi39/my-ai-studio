/**
 * 统一对话 Hook — 连接 /api/v1/travel/chat
 */

import { toast } from 'sonner';
import { useChatStore, type ReActStep, type ToolCall } from '@/features/travel/stores/useChatStore';
import { SSEClient } from '@/features/travel/services/sse/SSEClient';
import type { SSEEvent } from '@/features/travel/types/events';
import { TRAVEL_API_BASE, travelHeaders } from '@/features/travel/services/api/client';
import { useTravelRuntime } from '@/features/travel/TravelRuntimeContext';
import { useRef } from 'react';

export function useChat() {
  const { modelConfigId } = useTravelRuntime();
  const currentClientRef = useRef<SSEClient | null>(null);

  const sendMessage = async (text: string) => {
    if (!modelConfigId) {
      throw new Error('请先在设置中配置模型连接');
    }

    const {
      addMessage,
      updateMessage,
      setGenerating,
      setCurrentSessionId,
      bumpSessionList,
      chatMode: mode,
    } = useChatStore.getState();

    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
    });

    const assistantMessageId = `assistant-${Date.now()}`;
    addMessage({
      id: assistantMessageId,
      role: 'assistant',
      content: mode === 'agent' ? '🔄 正在连接 Agent…' : '🔄 正在思考…',
      mode,
      thinkingSteps: [],
      timestamp: Date.now(),
    });
    setGenerating(true);

    let contentBuffer = '';
    const thinkingSteps: ReActStep[] = [];
    const pendingToolCalls: Map<string, ToolCall> = new Map();
    let hasFinalResponse = false;
    let hasDoneEvent = false;

    const updateAssistant = (updates: Partial<{ content: string; thinkingSteps: ReActStep[] }>) => {
      updateMessage(assistantMessageId, updates);
    };

    const failAssistant = (message: string) => {
      updateAssistant({ content: `❌ ${message}` });
      toast.error(message);
      setGenerating(false);
    };

    const sessionIdForRequest = useChatStore.getState().currentSessionId;

    const client = new SSEClient({
      url: `${TRAVEL_API_BASE}/travel/chat`,
      method: 'POST',
      headers: travelHeaders(),
      body: JSON.stringify({
        message: text,
        mode,
        session_id: sessionIdForRequest,
        max_rounds: 3,
        model_config_id: modelConfigId,
      }),
      onEvent: (event: SSEEvent) => {
        if (event.type === 'session' && 'session_id' in event) {
          setCurrentSessionId(String(event.session_id));
          bumpSessionList();
        }

        if (event.type === 'start' && mode === 'agent') {
          updateAssistant({ content: '🔍 正在分析并调用工具，请稍候…' });
        }

        if (event.type === 'chunk' && 'content' in event && event.content) {
          contentBuffer += event.content;
          updateAssistant({ content: contentBuffer });
        }

        if (event.type === 'tool_call_start' && 'call_id' in event) {
          pendingToolCalls.set(event.call_id, {
            id: event.call_id,
            tool_name: event.tool_name,
            tool_args: event.tool_args,
            status: 'pending',
          });
        }

        if (event.type === 'tool_call_result' && 'call_id' in event) {
          const toolCall = pendingToolCalls.get(event.call_id);
          if (toolCall) {
            toolCall.result = event.result;
            toolCall.status = event.status;
            toolCall.duration_ms = event.duration_ms;
            toolCall.error = event.error;
          }
        }

        if (event.type === 'step' && 'step_type' in event && event.content) {
          if (event.step_type === 'Act') {
            const completedToolCalls = Array.from(pendingToolCalls.values()).filter(
              (tc) => tc.status !== 'pending',
            );
            thinkingSteps.push({
              type: event.step_type,
              content: event.content,
              round: event.round || 0,
              sequence: event.sequence || 0,
              toolCalls: completedToolCalls,
            });
            pendingToolCalls.clear();
          } else {
            thinkingSteps.push({
              type: event.step_type,
              content: event.content,
              round: event.round || 0,
              sequence: event.sequence || 0,
            });
          }

          if (mode === 'agent') {
            updateAssistant({
              content: '💭 正在推理中…',
              thinkingSteps: [...thinkingSteps],
            });
          }
        }

        if (event.type === 'final_response' && 'content' in event && event.content) {
          contentBuffer = event.content;
          hasFinalResponse = true;
          updateAssistant({ content: '✍️ 正在整理最终回复…', thinkingSteps: [...thinkingSteps] });
        }

        if (event.type === 'done') {
          hasDoneEvent = true;
          if (mode === 'agent') {
            if (!hasFinalResponse && !contentBuffer && thinkingSteps.length > 0) {
              const lastThinkStep = thinkingSteps.filter((s) => s.type === 'Think').pop();
              if (lastThinkStep) {
                contentBuffer = lastThinkStep.content;
              }
            }
            updateAssistant({
              content: contentBuffer || '已完成推理，但未生成最终回复。',
              thinkingSteps: [...thinkingSteps],
            });
          } else if (mode === 'llm') {
            updateAssistant({ content: contentBuffer || '无回复内容' });
          }
          setGenerating(false);
        }

        if (event.type === 'error' && 'message' in event) {
          failAssistant(event.message);
          pendingToolCalls.clear();
        }
      },
      onError: (error) => {
        failAssistant(error.message || '请求失败，请检查后端与模型配置');
      },
      onComplete: () => {
        const { isGenerating, setGenerating: stopGenerating } = useChatStore.getState();
        if (!hasDoneEvent && isGenerating) {
          failAssistant('连接已中断，未收到完整回复。请确认后端已启动并重试。');
        } else if (isGenerating) {
          stopGenerating(false);
        }
      },
    });

    currentClientRef.current = client;
    await client.start();
    currentClientRef.current = null;
  };

  const cancelCurrentRequest = () => {
    currentClientRef.current?.cancel();
    currentClientRef.current = null;
    useChatStore.getState().setGenerating(false);
  };

  return { sendMessage, cancelCurrentRequest };
}
