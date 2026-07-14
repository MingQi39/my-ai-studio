import { useRef } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import type { ChatToolRun } from '@/components/chat';
import { SSEClient } from '@/lib/sseClient';

import { useFitnessRuntime } from '@/features/fitness/FitnessRuntimeContext';
import { FITNESS_API_BASE, fitnessHeaders } from '@/features/fitness/services/api/client';
import {
  approveFitnessAgentAction,
  fetchFitnessTodaySummary,
} from '@/features/fitness/services/api/fitness';
import type { FitnessSSEEvent } from '@/features/fitness/types/events';
import { useFitnessChatStore } from '@/features/fitness/stores/useFitnessChatStore';
import { FITNESS_TOOL_LABELS } from '@/features/fitness/utils/fitnessUi';
import type { FitnessApprovalPreview } from '@/features/fitness/types/hitl';
import {
  buildApprovalPreviewFromToolArgs,
  isWriteTool,
} from '@/features/fitness/utils/fitnessHitl';

const SUMMARY_MUTATING_TOOLS = new Set([
  'set_daily_calorie_goal',
  'log_meal',
  'delete_diary_entry',
]);
const PROGRESS_SLOW_NOTICE_MS = 6000;

type SendMessageOptions = {
  agentMessage?: string;
};

function buildProgressText(
  t: (key: string, params?: Record<string, unknown>) => string,
  event: Extract<FitnessSSEEvent, { type: 'tool_progress' }>,
): string {
  const seq = event.index && event.total ? ` (${event.index}/${event.total})` : '';
  const foodSuffix = event.food_name ? `：${event.food_name}` : '';
  const stageMap: Record<string, string> = {
    parse_foods: t('fitness.chat.progress.parseFoods'),
    food_start: t('fitness.chat.progress.foodStart'),
    local_lookup: t('fitness.chat.progress.localLookup'),
    local_validate: t('fitness.chat.progress.localValidate'),
    usda_lookup: t('fitness.chat.progress.usdaLookup'),
    usda_validate: t('fitness.chat.progress.usdaValidate'),
    web_search: t('fitness.chat.progress.webSearch'),
    web_extract: t('fitness.chat.progress.webExtract'),
    llm_estimate: t('fitness.chat.progress.llmEstimate'),
  };
  const stageLabel = stageMap[event.stage] ?? t('fitness.chat.progress.working');
  return `${stageLabel}${seq}${foodSuffix}`;
}

export function useFitnessChat() {
  const { t } = useTranslation();
  const { modelConfigId } = useFitnessRuntime();
  const currentClientRef = useRef<SSEClient<FitnessSSEEvent> | null>(null);

  const refreshTodaySummary = () => {
    const { setTodaySummary } = useFitnessChatStore.getState();
    void fetchFitnessTodaySummary(null)
      .then((summary) => setTodaySummary(summary))
      .catch((e) => console.error(e));
  };

  const sendMessage = async (text: string, options?: SendMessageOptions) => {
    if (!modelConfigId) {
      throw new Error(t('fitness.chat.modelRequired'));
    }

    const agentMessage = options?.agentMessage ?? text;

    const {
      addMessage,
      updateMessage,
      setGenerating,
      setCurrentSessionId,
      bumpSessionList,
      setRecommendations,
      setPendingApproval,
    } = useFitnessChatStore.getState();

    setRecommendations([]);

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
    const toolRuns: ChatToolRun[] = [];
    const pendingTools = new Map<string, ChatToolRun>();
    const callIdToToolName = new Map<string, string>();

    const syncAssistant = (patch: {
      content?: string;
      statusLabel?: string;
      isThinking?: boolean;
      toolRuns?: ChatToolRun[];
    }) => {
      updateMessage(assistantMessageId, patch);
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
      const suffix = showSlowNotice ? ` ${t('fitness.chat.progress.slow')}` : '';
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

    const syncPendingApproval = (
      callId: string,
      toolName: string,
      toolArgs: Record<string, unknown>,
      preview?: FitnessApprovalPreview,
    ) => {
      setPendingApproval({
        callId,
        toolName,
        toolArgs,
        preview: preview ?? buildApprovalPreviewFromToolArgs(toolName, toolArgs),
        assistantMessageId,
      });
    };

    const client = new SSEClient<FitnessSSEEvent>({
      url: `${FITNESS_API_BASE}/agent/run`,
      method: 'POST',
      headers: fitnessHeaders(),
      body: JSON.stringify({
        message: agentMessage,
        session_id: useFitnessChatStore.getState().currentSessionId,
        max_rounds: 3,
        model_config_id: modelConfigId,
        timezone: null,
      }),
      onEvent: (event) => {
        if (event.type === 'session' && 'session_id' in event) {
          setCurrentSessionId(String(event.session_id));
          bumpSessionList();
        }

        if (event.type === 'start') {
          setWorkingStatus(t('fitness.chat.thinking'));
        }

        if (event.type === 'tool_call_start' && 'call_id' in event) {
          callIdToToolName.set(event.call_id, event.tool_name);
          const run: ChatToolRun = {
            call_id: event.call_id,
            tool_name: FITNESS_TOOL_LABELS[event.tool_name] ?? event.tool_name,
            tool_input: event.tool_args,
            status: 'running',
          };
          pendingTools.set(event.call_id, run);
          toolRuns.push(run);
          setWorkingStatus(
            t('fitness.chat.runningTool', {
              tool: FITNESS_TOOL_LABELS[event.tool_name] ?? event.tool_name,
            }),
          );

          if (isWriteTool(event.tool_name)) {
            syncPendingApproval(event.call_id, event.tool_name, event.tool_args);
          }
        }

        if (event.type === 'approval_required' && 'call_id' in event) {
          const run = pendingTools.get(event.call_id);
          if (run) {
            run.status = 'completed';
            run.tool_output = t('fitness.hitl.awaitingConfirmation');
          } else if (event.tool_name) {
            const run: ChatToolRun = {
              call_id: event.call_id,
              tool_name: FITNESS_TOOL_LABELS[event.tool_name] ?? event.tool_name,
              tool_input: event.tool_args,
              status: 'completed',
              tool_output: t('fitness.hitl.awaitingConfirmation'),
            };
            toolRuns.push(run);
            pendingTools.set(event.call_id, run);
            callIdToToolName.set(event.call_id, event.tool_name);
          }
          setPendingApproval({
            callId: event.call_id,
            toolName: event.tool_name,
            toolArgs: event.tool_args,
            preview: event.preview,
            assistantMessageId,
          });
          syncAssistant({
            statusLabel: undefined,
            isThinking: false,
            toolRuns: [...toolRuns],
          });
        }

        if (event.type === 'tool_call_result' && 'call_id' in event) {
          const run = pendingTools.get(event.call_id);
          if (run) {
            if (event.status === 'pending_approval') {
              run.status = 'completed';
              run.tool_output = t('fitness.hitl.awaitingConfirmation');
              const rawToolName = callIdToToolName.get(event.call_id);
              if (rawToolName && !useFitnessChatStore.getState().pendingApproval) {
                const toolArgs = (run.tool_input ?? {}) as Record<string, unknown>;
                syncPendingApproval(event.call_id, rawToolName, toolArgs);
              }
            } else {
              run.status = event.status === 'error' ? 'error' : 'completed';
              run.tool_output =
                typeof event.result === 'string'
                  ? event.result
                  : JSON.stringify(event.result ?? event.error ?? '', null, 2);
            }
          }
          const rawToolName = callIdToToolName.get(event.call_id);
          if (
            event.status === 'success' &&
            rawToolName &&
            SUMMARY_MUTATING_TOOLS.has(rawToolName)
          ) {
            refreshTodaySummary();
          }
          if (event.status !== 'pending_approval') {
            setWorkingStatus(contentBuffer || t('fitness.chat.thinking'));
          }
        }

        if (event.type === 'tool_progress') {
          setWorkingStatus(buildProgressText(t, event));
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

        if (event.type === 'meal_logged') {
          toast.success(t('fitness.chat.mealLogged'));
        }

        if (event.type === 'recommendations') {
          useFitnessChatStore.getState().setRecommendations(event.recommendations ?? []);
        }

        if (event.type === 'done') {
          clearProgressTimeout();
          showSlowNotice = false;
          hasDoneEvent = true;
          if (!contentBuffer && !useFitnessChatStore.getState().pendingApproval) {
            contentBuffer = t('fitness.chat.emptyReply');
          }
          syncAssistant({
            content: contentBuffer,
            statusLabel: undefined,
            isThinking: false,
            toolRuns: [...toolRuns],
          });
          setGenerating(false);
        }

        if (event.type === 'error') {
          clearProgressTimeout();
          showSlowNotice = false;
          const msg = event.message || t('fitness.chat.requestFailed');
          toast.error(msg);
          syncAssistant({
            content: `❌ ${msg}`,
            statusLabel: undefined,
            isThinking: false,
            toolRuns: [...toolRuns],
          });
          setGenerating(false);
        }
      },
      onError: (error) => {
        clearProgressTimeout();
        showSlowNotice = false;
        toast.error(error.message || t('fitness.chat.requestFailed'));
        syncAssistant({
          content: `❌ ${error.message}`,
          statusLabel: undefined,
          isThinking: false,
          toolRuns: [...toolRuns],
        });
        setGenerating(false);
      },
      onComplete: () => {
        clearProgressTimeout();
        showSlowNotice = false;
        if (!hasDoneEvent) {
          syncAssistant({
            content: t('fitness.chat.streamInterrupted'),
            statusLabel: undefined,
            isThinking: false,
            toolRuns: [...toolRuns],
          });
          setGenerating(false);
        }
      },
    });

    currentClientRef.current = client;
    try {
      await client.start();
    } finally {
      clearProgressTimeout();
      currentClientRef.current = null;
    }
  };

  const approvePending = async (userAckText?: string) => {
    const { pendingApproval, currentSessionId, setPendingApproval, addMessage, setGenerating } =
      useFitnessChatStore.getState();

    if (!pendingApproval) return;

    if (typeof userAckText === 'string' && userAckText.trim()) {
      addMessage({
        id: `user-ack-${Date.now()}`,
        role: 'user',
        content: userAckText.trim(),
      });
    }

    setGenerating(true);
    try {
      const response = await approveFitnessAgentAction({
        session_id: currentSessionId,
        tool_name: pendingApproval.toolName,
        tool_args: pendingApproval.toolArgs,
        call_id: pendingApproval.callId,
      });

      setPendingApproval(null);
      refreshTodaySummary();

      if (pendingApproval.toolName === 'log_meal') {
        toast.success(t('fitness.chat.mealLogged'));
      } else if (pendingApproval.toolName === 'set_daily_calorie_goal') {
        toast.success(t('fitness.hitl.goalUpdated'));
      } else if (pendingApproval.toolName === 'delete_diary_entry') {
        toast.success(t('fitness.hitl.entryDeleted'));
      }

      addMessage({
        id: `assistant-approved-${Date.now()}`,
        role: 'assistant',
        content: response.message,
        isThinking: false,
      });
    } catch (error) {
      console.error(error);
      toast.error(error instanceof Error ? error.message : t('fitness.hitl.approveFailed'));
    } finally {
      setGenerating(false);
    }
  };

  const cancelPendingApproval = (userAckText?: string) => {
    const { pendingApproval, setPendingApproval, addMessage } = useFitnessChatStore.getState();
    if (!pendingApproval) return;
    if (typeof userAckText === 'string' && userAckText.trim()) {
      addMessage({
        id: `user-ack-${Date.now()}`,
        role: 'user',
        content: userAckText.trim(),
      });
    }
    setPendingApproval(null);
    addMessage({
      id: `assistant-cancel-${Date.now()}`,
      role: 'assistant',
      content: t('fitness.hitl.cancelled'),
      isThinking: false,
    });
  };

  const cancelCurrentRequest = () => {
    currentClientRef.current?.cancel();
    currentClientRef.current = null;

    const { messages, updateMessage, setGenerating } = useFitnessChatStore.getState();
    const thinkingPlaceholder = t('fitness.chat.thinking');
    const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant' && m.isThinking);
    if (lastAssistant) {
      const content =
        lastAssistant.content && lastAssistant.content !== thinkingPlaceholder
          ? lastAssistant.content
          : t('chat.generationStopped');
      updateMessage(lastAssistant.id, {
        content,
        statusLabel: undefined,
        isThinking: false,
      });
    }
    setGenerating(false);
  };

  return { sendMessage, approvePending, cancelPendingApproval, cancelCurrentRequest };
}
