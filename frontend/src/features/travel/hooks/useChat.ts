/**
 * Unified travel chat hook with refresh-safe SSE replay.
 */

import { useRef } from 'react';
import { toast } from 'sonner';

import {
  cancelResumableAgentStream,
  fetchResumableAgentStreamStatus,
} from '@/lib/resumableAgentStream';
import { SSEClient } from '@/features/travel/services/sse/SSEClient';
import { TRAVEL_API_BASE, travelHeaders } from '@/features/travel/services/api/client';
import { useChatStore, type Message } from '@/features/travel/stores/useChatStore';
import {
  createTravelStreamState,
  reduceTravelStreamEvent,
} from '@/features/travel/streams/travelStreamReducer';
import type { SSEEvent } from '@/features/travel/types/events';
import { useTravelRuntime } from '@/features/travel/TravelRuntimeContext';

type RunStreamOptions = {
  url: string;
  method: 'GET' | 'POST';
  body?: string;
  assistantMessageId: string;
  mode: 'llm' | 'agent';
};

export function useChat() {
  const { modelConfigId } = useTravelRuntime();
  const currentClientRef = useRef<SSEClient | null>(null);

  const runStream = async ({
    url,
    method,
    body,
    assistantMessageId,
    mode,
  }: RunStreamOptions) => {
    const streamState = createTravelStreamState(mode);
    const {
      updateMessage,
      setGenerating,
      setCurrentSessionId,
      bumpSessionList,
    } = useChatStore.getState();

    const failAssistant = (message: string) => {
      updateMessage(assistantMessageId, { content: `❌ ${message}` });
      toast.error(message);
      setGenerating(false);
    };

    const client = new SSEClient({
      url,
      method,
      headers: travelHeaders(),
      body,
      onEvent: (event: SSEEvent) => {
        const effect = reduceTravelStreamEvent(streamState, event);
        if (effect.sessionId) {
          setCurrentSessionId(effect.sessionId);
          bumpSessionList();
        }
        if (effect.message) {
          updateMessage(assistantMessageId, effect.message);
        }
        if (effect.error) {
          failAssistant(effect.error);
        }
        if (effect.done) {
          setGenerating(false);
        }
      },
      onError: (error) => {
        failAssistant(error.message || '请求失败，请检查后端与模型配置');
      },
      onComplete: () => {
        const { isGenerating, setGenerating: stopGenerating } = useChatStore.getState();
        if (!streamState.hasDoneEvent && isGenerating) {
          failAssistant('连接已中断，生成任务仍在后台运行；刷新页面可自动恢复。');
        } else if (isGenerating) {
          stopGenerating(false);
        }
      },
    });

    currentClientRef.current = client;
    try {
      await client.start();
    } finally {
      if (currentClientRef.current === client) {
        currentClientRef.current = null;
      }
    }
  };

  const sendMessage = async (text: string) => {
    if (!modelConfigId) {
      throw new Error('请先在设置中配置模型连接');
    }

    const {
      addMessage,
      setGenerating,
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

    await runStream({
      url: `${TRAVEL_API_BASE}/travel/chat`,
      method: 'POST',
      body: JSON.stringify({
        message: text,
        mode,
        session_id: useChatStore.getState().currentSessionId,
        max_rounds: 3,
        model_config_id: modelConfigId,
      }),
      assistantMessageId,
      mode,
    });
  };

  const resumeActiveGeneration = async (
    sessionId: string,
    restoredMessages: Message[],
  ): Promise<boolean> => {
    const status = await fetchResumableAgentStreamStatus(
      `${TRAVEL_API_BASE}/travel/chat/status/${sessionId}`,
      travelHeaders(),
    );
    if (!status.is_streaming) return false;
    if (useChatStore.getState().currentSessionId !== sessionId) return false;

    const mode = status.metadata.mode === 'llm' ? 'llm' : 'agent';
    const assistantMessageId = `assistant-resume-${sessionId}`;
    useChatStore.getState().setMessages([
      ...restoredMessages,
      {
        id: assistantMessageId,
        role: 'assistant',
        content: mode === 'agent' ? '🔄 正在恢复 Agent…' : '🔄 正在恢复回复…',
        mode,
        thinkingSteps: [],
        timestamp: Date.now(),
      },
    ]);
    useChatStore.getState().setGenerating(true);

    await runStream({
      url: `${TRAVEL_API_BASE}/travel/chat/resume/${sessionId}`,
      method: 'GET',
      assistantMessageId,
      mode,
    });
    return true;
  };

  const cancelCurrentRequest = () => {
    currentClientRef.current?.cancel();
    currentClientRef.current = null;

    const { currentSessionId, messages, updateMessage, setGenerating } = useChatStore.getState();
    if (currentSessionId) {
      void cancelResumableAgentStream(
        `${TRAVEL_API_BASE}/travel/chat/cancel/${currentSessionId}`,
        travelHeaders(),
      ).catch((error) => console.error('Failed to cancel travel generation:', error));
    }
    const thinkingMarkers = [
      '🔄 正在连接 Agent…',
      '🔄 正在思考…',
      '🔄 正在恢复 Agent…',
      '🔄 正在恢复回复…',
      '🔍 正在分析并调用工具，请稍候…',
      '💭 正在推理中…',
      '✍️ 正在整理最终回复…',
    ];
    const lastAssistant = [...messages].reverse().find((message) => message.role === 'assistant');
    if (lastAssistant) {
      const hasPartialContent =
        Boolean(lastAssistant.content)
        && !thinkingMarkers.includes(lastAssistant.content)
        && !lastAssistant.content.startsWith('❌');
      updateMessage(lastAssistant.id, {
        content: hasPartialContent ? lastAssistant.content : '已停止生成',
      });
    }
    setGenerating(false);
  };

  return { sendMessage, resumeActiveGeneration, cancelCurrentRequest };
}
