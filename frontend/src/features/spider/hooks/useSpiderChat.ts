import { useRef } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import type { ChatToolRun } from '@/components/chat';
import type { StudioChatMessage } from '@/hooks/studioChat/types';
import { SSEClient } from '@/lib/sseClient';
import {
  cancelResumableAgentStream,
  fetchResumableAgentStreamStatus,
} from '@/lib/resumableAgentStream';

import { useSpiderRuntime } from '@/features/spider/SpiderRuntimeContext';
import { SPIDER_API_BASE, spiderHeaders } from '@/features/spider/services/api/client';
import type { SpiderSSEEvent } from '@/features/spider/types/events';
import { normalizeSpiderTodos, type SpiderTodoItem } from '@/features/spider/types/todo';
import { useSpiderChatStore } from '@/features/spider/stores/useSpiderChatStore';
import { useSpiderWorkspace } from '@/features/spider/hooks/useSpiderWorkspace';
import { findResumableMessage } from '@/features/spider/utils/resumableMessage';

const PROGRESS_SLOW_NOTICE_MS = 8000;

export function useSpiderChat() {
  const { t } = useTranslation();
  const { modelConfigId } = useSpiderRuntime();
  const { refreshWorkspace } = useSpiderWorkspace();
  const currentClientRef = useRef<SSEClient<SpiderSSEEvent> | null>(null);

  const startRun = async (params: {
    text: string;
    assistantMessageId: string;
    appendUserMessage: boolean;
    resume: boolean;
    seedToolRuns?: ChatToolRun[];
    seedTodos?: SpiderTodoItem[];
    streamUrl?: string;
    streamMethod?: 'GET' | 'POST';
  }) => {
    const {
      addMessage,
      updateMessage,
      setGenerating,
      setCurrentSessionId,
      bumpSessionList,
      targetUrl,
      cookies,
    } = useSpiderChatStore.getState();

    const { text, assistantMessageId, appendUserMessage, resume } = params;

    if (appendUserMessage) {
      addMessage({
        id: `user-${Date.now()}`,
        role: 'user',
        content: text,
      });
      addMessage({
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        isThinking: true,
        toolRuns: [],
      });
    } else {
      // Resume: reuse the interrupted/failed bubble and let the stream advance
      // it in place (clearing the failure card and reviving the thinking state).
      updateMessage(assistantMessageId, {
        isThinking: true,
        statusLabel: undefined,
        failure: undefined,
      });
    }

    setGenerating(true);

    let contentBuffer = '';
    let hasDoneEvent = false;
    let hasErrorEvent = false;
    const toolRuns: ChatToolRun[] = params.seedToolRuns ? [...params.seedToolRuns] : [];
    const pendingTools = new Map<string, ChatToolRun>(
      toolRuns
        .filter((run) => run.call_id)
        .map((run) => [String(run.call_id), run]),
    );
    let todos: SpiderTodoItem[] | undefined = params.seedTodos;

    const syncAssistant = (patch: {
      content?: string;
      statusLabel?: string;
      isThinking?: boolean;
      toolRuns?: ChatToolRun[];
      failure?: StudioChatMessage['failure'];
      todos?: SpiderTodoItem[];
    }) => {
      updateMessage(assistantMessageId, {
        ...patch,
        ...(todos ? { todos } : {}),
      });
    };

    let progressTimeout: ReturnType<typeof setTimeout> | null = null;
    let currentWorkingText = '';
    let showSlowNotice = false;

    const clearProgressTimeout = () => {
      if (progressTimeout) {
        clearTimeout(progressTimeout);
        progressTimeout = null;
      }
    };

    const syncWorkingStatus = () => {
      const suffix = showSlowNotice ? ` ${t('spider.chat.progress.slow')}` : '';
      syncAssistant({
        content: '',
        statusLabel: `${currentWorkingText}${suffix}`,
        isThinking: true,
        toolRuns: [...toolRuns],
      });
    };

    const setWorkingStatus = (text: string) => {
      currentWorkingText = text;
      showSlowNotice = false;
      syncWorkingStatus();
      clearProgressTimeout();
      progressTimeout = setTimeout(() => {
        showSlowNotice = true;
        syncWorkingStatus();
      }, PROGRESS_SLOW_NOTICE_MS);
    };

    const client = new SSEClient<SpiderSSEEvent>({
      url: params.streamUrl ?? `${SPIDER_API_BASE}/agent/run`,
      method: params.streamMethod ?? 'POST',
      headers: spiderHeaders(),
      body:
        params.streamMethod === 'GET'
          ? undefined
          : JSON.stringify({
              message: text,
              session_id: useSpiderChatStore.getState().currentSessionId,
              model_config_id: modelConfigId,
              target_url: targetUrl || null,
              cookies: cookies.trim() || null,
              resume,
            }),
      onEvent: (event) => {
        if (event.type === 'session' && 'session_id' in event) {
          const sessionId = String(event.session_id);
          setCurrentSessionId(sessionId);
          if (targetUrl.trim()) {
            useSpiderChatStore.getState().setTargetUrl(targetUrl);
          }
          bumpSessionList();
        }

        if (event.type === 'start') {
          setWorkingStatus(t('spider.chat.thinking'));
        }

        if (event.type === 'tool_call_start' && 'call_id' in event) {
          const run =
            pendingTools.get(event.call_id)
            ?? {
              call_id: event.call_id,
              tool_name: event.tool_name,
              status: 'running' as const,
            };
          run.tool_name = event.tool_name;
          run.raw_tool_name = event.raw_tool_name;
          run.tool_input = event.tool_args;
          run.status = 'running';
          if (!pendingTools.has(event.call_id)) {
            toolRuns.push(run);
          }
          pendingTools.set(event.call_id, run);
          setWorkingStatus(t('spider.chat.runningTool', { tool: event.tool_name }));
        }

        if (event.type === 'todos_updated') {
          const next = normalizeSpiderTodos(event.todos);
          if (next.length > 0) {
            todos = next;
            syncAssistant({
              content: contentBuffer,
              statusLabel: currentWorkingText || undefined,
              isThinking: true,
              toolRuns: [...toolRuns],
            });
          }
        }

        if (event.type === 'subagent_start' && event.subagent) {
          setWorkingStatus(
            t('spider.chat.subagentWorking', {
              name: event.subagent,
            }),
          );
        }

        if (event.type === 'tool_call_result' && 'call_id' in event) {
          const run = pendingTools.get(event.call_id);
          if (run) {
            run.status = event.status === 'error' ? 'error' : 'completed';
            run.tool_output =
              typeof event.result === 'string'
                ? event.result
                : JSON.stringify(event.result ?? '', null, 2);
          }
          setWorkingStatus(contentBuffer || t('spider.chat.thinking'));
        }

        if (event.type === 'chunk' && event.content) {
          clearProgressTimeout();
          showSlowNotice = false;
          contentBuffer += event.content;
          syncAssistant({
            content: contentBuffer,
            statusLabel: undefined,
            isThinking: true,
            toolRuns: [...toolRuns],
          });
        }

        if (event.type === 'final_response' && event.content) {
          clearProgressTimeout();
          showSlowNotice = false;
          contentBuffer = event.content;
          syncAssistant({
            content: contentBuffer,
            statusLabel: undefined,
            isThinking: false,
            toolRuns: [...toolRuns],
          });
        }

        if (event.type === 'subagent_complete') {
          void refreshWorkspace();
        }

        if (event.type === 'workspace_updated') {
          const { currentSessionId, generatingSessionId, setWorkspaceFiles } =
            useSpiderChatStore.getState();
          // Ignore file updates while viewing a different session.
          if (generatingSessionId && currentSessionId !== generatingSessionId) {
            return;
          }
          if (Array.isArray(event.files)) {
            setWorkspaceFiles(
              event.files.map((file) => ({
                name: file.name,
                size: file.size,
                modified_at: file.modified_at ?? null,
              })),
            );
          } else {
            void refreshWorkspace();
          }
        }

        if (event.type === 'error') {
          hasErrorEvent = true;
          const title = event.title || t('spider.chat.error');
          const detail = event.detail || event.message || '';
          const hints = Array.isArray(event.hints)
            ? event.hints.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
            : [];
          toast.error(title);
          contentBuffer = event.message || title;
          syncAssistant({
            content: '',
            statusLabel: undefined,
            isThinking: false,
            toolRuns: [...toolRuns],
            failure: {
              code: event.code,
              title,
              detail: detail || undefined,
              hints: hints.length > 0 ? hints : undefined,
              stage: event.stage,
              recoverable: event.recoverable,
            },
          });
        }

        if (event.type === 'done') {
          hasDoneEvent = true;
          clearProgressTimeout();
          showSlowNotice = false;
          if (!hasErrorEvent) {
            syncAssistant({
              content: contentBuffer || t('spider.chat.done'),
              statusLabel: undefined,
              isThinking: false,
              toolRuns: [...toolRuns],
            });
          }
          setGenerating(false);
        }
      },
      onError: (error) => {
        console.error(error);
        toast.error(t('spider.chat.streamError'));
        syncAssistant({
          content: t('spider.chat.streamError'),
          statusLabel: undefined,
          isThinking: false,
          toolRuns: [...toolRuns],
        });
        setGenerating(false);
      },
      onComplete: () => {
        if (!hasDoneEvent) {
          setGenerating(false);
        }
      },
    });

    currentClientRef.current = client;
    await client.start();
    currentClientRef.current = null;
  };

  const sendMessage = async (text: string) => {
    if (!modelConfigId) {
      throw new Error(t('spider.chat.modelRequired'));
    }
    await startRun({
      text,
      assistantMessageId: `assistant-${Date.now()}`,
      appendUserMessage: true,
      resume: false,
    });
  };

  const resumeTask = async () => {
    if (!modelConfigId) {
      throw new Error(t('spider.chat.modelRequired'));
    }
    const { messages } = useSpiderChatStore.getState();
    const target = findResumableMessage(messages);
    if (!target) return;
    const lastUser = [...messages].reverse().find((m) => m.role === 'user');
    const text = lastUser?.content?.trim() || t('spider.chat.resumeTask');

    useSpiderChatStore.getState().setRestoreInterruptedHint(false);
    await startRun({
      text,
      assistantMessageId: target.id,
      appendUserMessage: false,
      resume: true,
      seedToolRuns: target.toolRuns,
      seedTodos: target.todos,
    });
  };

  const resumeActiveGeneration = async (
    sessionId: string,
    restoredMessages: StudioChatMessage[],
  ): Promise<boolean> => {
    const status = await fetchResumableAgentStreamStatus(
      `${SPIDER_API_BASE}/agent/status/${sessionId}`,
      spiderHeaders(),
    );
    if (!status.is_streaming) return false;
    if (useSpiderChatStore.getState().currentSessionId !== sessionId) return false;

    const existing = [...restoredMessages]
      .reverse()
      .find((message) => message.role === 'assistant' && message.isComplete === false);
    const assistantMessageId = existing?.id ?? `assistant-resume-${sessionId}`;

    if (existing) {
      useSpiderChatStore.getState().setMessages(
        restoredMessages.map((message) =>
          message.id === assistantMessageId
            ? {
                ...message,
                content: '',
                isThinking: true,
                statusLabel: t('spider.chat.thinking'),
                toolRuns: message.toolRuns,
                failure: undefined,
              }
            : message,
        ),
      );
    } else {
      useSpiderChatStore.getState().setMessages([
        ...restoredMessages,
        {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          isThinking: true,
          statusLabel: t('spider.chat.thinking'),
          toolRuns: [],
        },
      ]);
    }

    useSpiderChatStore.getState().setRestoreInterruptedHint(false);
    await startRun({
      text: '',
      assistantMessageId,
      appendUserMessage: false,
      resume: false,
      seedToolRuns: existing?.toolRuns,
      seedTodos: existing?.todos,
      streamUrl: `${SPIDER_API_BASE}/agent/resume/${sessionId}`,
      streamMethod: 'GET',
    });
    return true;
  };

  const cancelCurrentRequest = () => {
    currentClientRef.current?.cancel();
    currentClientRef.current = null;
    const { currentSessionId } = useSpiderChatStore.getState();
    if (currentSessionId) {
      void cancelResumableAgentStream(
        `${SPIDER_API_BASE}/agent/cancel/${currentSessionId}`,
        spiderHeaders(),
      ).catch((error) => console.error('Failed to cancel spider generation:', error));
    }
    useSpiderChatStore.getState().setGenerating(false);
  };

  return { sendMessage, resumeTask, resumeActiveGeneration, cancelCurrentRequest };
}
