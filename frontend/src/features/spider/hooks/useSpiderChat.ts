import { useRef } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import type { ChatToolRun } from '@/components/chat';
import type { StudioChatMessage } from '@/hooks/studioChat/types';
import { SSEClient } from '@/lib/sseClient';

import { useSpiderRuntime } from '@/features/spider/SpiderRuntimeContext';
import { SPIDER_API_BASE, spiderHeaders } from '@/features/spider/services/api/client';
import type { SpiderSSEEvent } from '@/features/spider/types/events';
import { normalizeSpiderTodos, type SpiderTodoItem } from '@/features/spider/types/todo';
import { useSpiderChatStore } from '@/features/spider/stores/useSpiderChatStore';
import { useSpiderWorkspace } from '@/features/spider/hooks/useSpiderWorkspace';

const PROGRESS_SLOW_NOTICE_MS = 8000;

export function useSpiderChat() {
  const { t } = useTranslation();
  const { modelConfigId } = useSpiderRuntime();
  const { refreshWorkspace } = useSpiderWorkspace();
  const currentClientRef = useRef<SSEClient<SpiderSSEEvent> | null>(null);

  const sendMessage = async (text: string) => {
    if (!modelConfigId) {
      throw new Error(t('spider.chat.modelRequired'));
    }

    const {
      addMessage,
      updateMessage,
      setGenerating,
      setCurrentSessionId,
      bumpSessionList,
      targetUrl,
    } = useSpiderChatStore.getState();

    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
    });

    const assistantMessageId = `assistant-${Date.now()}`;
    addMessage({
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      isThinking: true,
      toolRuns: [],
    });

    setGenerating(true);

    let contentBuffer = '';
    let hasDoneEvent = false;
    let hasErrorEvent = false;
    const toolRuns: ChatToolRun[] = [];
    const pendingTools = new Map<string, ChatToolRun>();
    let todos: SpiderTodoItem[] | undefined;

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
      url: `${SPIDER_API_BASE}/agent/run`,
      method: 'POST',
      headers: spiderHeaders(),
      body: JSON.stringify({
        message: text,
        session_id: useSpiderChatStore.getState().currentSessionId,
        model_config_id: modelConfigId,
        target_url: targetUrl || null,
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
          const run: ChatToolRun = {
            call_id: event.call_id,
            tool_name: event.tool_name,
            raw_tool_name: event.raw_tool_name,
            tool_input: event.tool_args,
            status: 'running',
          };
          pendingTools.set(event.call_id, run);
          toolRuns.push(run);
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
          if (Array.isArray(event.files)) {
            useSpiderChatStore.getState().setWorkspaceFiles(
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

  const cancelCurrentRequest = () => {
    currentClientRef.current?.cancel();
    currentClientRef.current = null;
    useSpiderChatStore.getState().setGenerating(false);
  };

  return { sendMessage, cancelCurrentRequest };
}
