import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import {
  ChatEmptyState,
  ChatJumpToBottom,
  QueuedChatInput,
  StudioChatMessageList,
} from '@/components/chat';
import { useChatAutoScroll } from '@/hooks/useChatAutoScroll';
import { FitnessApprovalCard } from '@/features/fitness/components/FitnessApprovalCard';
import { FitnessRecommendationCards } from '@/features/fitness/components/FitnessRecommendationCards';
import { FitnessTodayStrip } from '@/features/fitness/components/FitnessTodayStrip';
import { fitnessBranding } from '@/features/fitness/config/branding';
import { useFitnessChat } from '@/features/fitness/hooks/useFitnessChat';
import { useFitnessSessionRestore } from '@/features/fitness/hooks/useFitnessSessionRestore';
import { useFitnessSessionRoute } from '@/features/fitness/hooks/useFitnessSessionRoute';
import { useFitnessTodaySummary } from '@/features/fitness/hooks/useFitnessTodaySummary';
import { useFitnessChatStore } from '@/features/fitness/stores/useFitnessChatStore';
import type { FitnessGuidedFlowId } from '@/features/fitness/types/hitl';
import { isApprovalCancel, isApprovalConfirm } from '@/features/fitness/utils/fitnessHitl';

export function FitnessChatView({
  isDarkMode,
  isControlPanelOpen,
  onOpenPanel,
}: {
  isDarkMode: boolean;
  selectedModel?: string;
  onOpenModelSettings?: () => void;
  isControlPanelOpen?: boolean;
  onOpenPanel?: () => void;
}) {
  const { t } = useTranslation();
  const messages = useFitnessChatStore((s) => s.messages);
  const isGenerating = useFitnessChatStore((s) => s.isGenerating);
  const isLoadingHistory = useFitnessChatStore((s) => s.isLoadingHistory);
  const recommendations = useFitnessChatStore((s) => s.recommendations);
  const currentSessionId = useFitnessChatStore((s) => s.currentSessionId);
  const guidedFlow = useFitnessChatStore((s) => s.guidedFlow);
  const pendingApproval = useFitnessChatStore((s) => s.pendingApproval);
  const addMessage = useFitnessChatStore((s) => s.addMessage);
  const setGuidedFlow = useFitnessChatStore((s) => s.setGuidedFlow);

  const { todaySummary } = useFitnessTodaySummary(true);
  useFitnessSessionRoute();

  const {
    sendMessage,
    resumeActiveGeneration,
    approvePending,
    cancelPendingApproval,
    cancelCurrentRequest,
  } = useFitnessChat();
  useFitnessSessionRestore(resumeActiveGeneration);
  const [inputValue, setInputValue] = useState('');

  const { scrollContainerRef, scrollSentinelRef, showJumpButton, scrollToBottom } = useChatAutoScroll({
    deps: [messages, isGenerating, recommendations, pendingApproval],
    active: messages.length > 0,
    resetKey: currentSessionId,
  });

  const remainingKcal = Math.max(
    0,
    Math.round(todaySummary?.remaining_kcal ?? todaySummary?.daily_calorie_goal ?? 1800),
  );
  const dailyGoal = Math.round(todaySummary?.daily_calorie_goal ?? 1800);

  const inputPlaceholder = useMemo(() => {
    if (pendingApproval) return t('fitness.hitl.replyPlaceholder');
    if (!guidedFlow) return t('fitness.chat.placeholder');
    return t(`fitness.prompts.${guidedFlow}.placeholder`);
  }, [guidedFlow, pendingApproval, t]);

  useEffect(() => {
    if (pendingApproval) {
      scrollToBottom('smooth');
    }
  }, [pendingApproval, scrollToBottom]);

  const startGuidedFlow = (flowId: FitnessGuidedFlowId) => {
    const question = t(`fitness.prompts.${flowId}.question`, {
      remaining: remainingKcal,
      goal: dailyGoal,
    });
    addMessage({
      id: `guide-${Date.now()}`,
      role: 'assistant',
      content: question,
      isThinking: false,
    });
    setGuidedFlow(flowId);
    scrollToBottom('auto');
  };

  const handleSend = async (text: string) => {
    const content = (text ?? inputValue).trim();
    if (!content) return;

    if (pendingApproval) {
      setInputValue('');
      scrollToBottom('auto');
      if (isApprovalConfirm(content)) {
        void approvePending(content).catch((err) => {
          console.error(err);
          toast.error(err instanceof Error ? err.message : t('fitness.hitl.approveFailed'));
        });
        return;
      }
      if (isApprovalCancel(content)) {
        cancelPendingApproval(content);
        return;
      }
      toast.message(t('fitness.hitl.replyHint'));
      return;
    }

    const activeFlow = guidedFlow;
    setInputValue('');
    setGuidedFlow(null);
    scrollToBottom('auto');

    const agentMessage = activeFlow
      ? t(`fitness.prompts.${activeFlow}.sendTemplate`, {
          answer: content.trim(),
          remaining: remainingKcal,
          goal: dailyGoal,
        })
      : undefined;

    try {
      await sendMessage(content, agentMessage ? { agentMessage } : undefined);
    } catch (err) {
      console.error(err);
      toast.error(err instanceof Error ? err.message : t('fitness.chat.sendFailed'));
    }
  };

  const handleSendPayload = async (content: string) => {
    await handleSend(content);
  };

  const quickPrompts = [
    {
      id: 'p1',
      title: t('fitness.prompts.logLunch.title'),
      description: t('fitness.prompts.logLunch.desc'),
      onSelect: () => startGuidedFlow('logLunch'),
    },
    {
      id: 'p2',
      title: t('fitness.prompts.recommend.title'),
      description: t('fitness.prompts.recommend.desc', { remaining: remainingKcal }),
      onSelect: () => startGuidedFlow('recommend'),
    },
    {
      id: 'p3',
      title: t('fitness.prompts.setGoal.title'),
      description: t('fitness.prompts.setGoal.desc'),
      onSelect: () => startGuidedFlow('setGoal'),
    },
  ];

  return (
    <div className="flex-1 flex flex-col w-full h-full relative">
      {!isControlPanelOpen && (
        <FitnessTodayStrip summary={todaySummary} onOpenPanel={onOpenPanel} />
      )}

      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto w-full flex flex-col items-center">
        {messages.length === 0 ? (
          <ChatEmptyState
            loading={isLoadingHistory}
            loadingMessage={t('fitness.chat.loadingHistory')}
            logoAlt={fitnessBranding.logoAlt}
            title={fitnessBranding.tagline}
            subtitle={fitnessBranding.subtitle}
            quickPrompts={quickPrompts}
            variant="travel"
          />
        ) : (
          <div className="w-full">
            <FitnessRecommendationCards
              recommendations={recommendations}
              disabled={isGenerating}
              onConfirm={(idx) => handleSend(t('fitness.chat.confirmMeal', { index: idx + 1 }))}
            />

            <StudioChatMessageList
              messages={messages}
              isDarkMode={isDarkMode}
              scrollSentinelRef={scrollSentinelRef}
            />
          </div>
        )}
        {messages.length === 0 && <div ref={scrollSentinelRef} className="h-px w-full shrink-0" aria-hidden />}
      </div>

      {showJumpButton && messages.length > 0 && (
        <ChatJumpToBottom onClick={() => scrollToBottom('smooth')} />
      )}

      <div className="w-full mx-auto px-3 sm:px-4 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 shrink-0 bg-gradient-to-t from-[var(--bg-main)] via-[var(--bg-main)] to-transparent relative z-20">
        <div className="max-w-4xl mx-auto space-y-2">
          {pendingApproval && (
            <FitnessApprovalCard
              approval={pendingApproval}
              disabled={isGenerating}
              onConfirm={() => {
                void approvePending().catch((err) => {
                  console.error(err);
                  toast.error(err instanceof Error ? err.message : t('fitness.hitl.approveFailed'));
                });
              }}
              onCancel={() => cancelPendingApproval()}
            />
          )}

          <QueuedChatInput
            layout="travel"
            value={inputValue}
            onChange={setInputValue}
            isBusy={isGenerating}
            onStop={cancelCurrentRequest}
            getPayload={(value) => value.trim() || null}
            onSendPayload={handleSendPayload}
            getQueuedLabel={(payload) => payload}
            onQueuedEdit={(payload) => setInputValue(payload)}
            shouldBypassQueue={(text) =>
              !!pendingApproval && (isApprovalConfirm(text) || isApprovalCancel(text))
            }
            placeholder={inputPlaceholder}
            innerClassName="flex flex-col relative w-full shadow-sm bg-white dark:bg-[#1E293B] border border-slate-300 dark:border-slate-700 rounded-2xl focus-within:ring-2 focus-within:ring-emerald-500/40 focus-within:border-emerald-500 transition-all overflow-hidden"
            textareaRows={2}
          />

          <div className="flex items-start gap-2 px-1 text-[11px] text-[var(--text-secondary)] leading-relaxed">
            <AlertCircle size={13} className="shrink-0 mt-0.5 text-amber-500" />
            <span>{t('fitness.disclaimer')}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
