import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import {
  ChatJumpToBottom,
  QueuedChatInput,
  StudioChatMessageList,
} from '@/components/chat';
import { useChatAutoScroll } from '@/hooks/useChatAutoScroll';
import { SpiderEmptyState } from '@/features/spider/components/SpiderEmptyState';
import { SpiderFailureCard } from '@/features/spider/components/SpiderFailureCard';
import { useSpiderChat } from '@/features/spider/hooks/useSpiderChat';
import { useSpiderSessionRestore } from '@/features/spider/hooks/useSpiderSessionRestore';
import { useSpiderSessionRoute } from '@/features/spider/hooks/useSpiderSessionRoute';
import { useSpiderWorkspace } from '@/features/spider/hooks/useSpiderWorkspace';
import { useSpiderChatStore } from '@/features/spider/stores/useSpiderChatStore';
import { findResumableMessage } from '@/features/spider/utils/resumableMessage';

export function SpiderChatView({
  isDarkMode,
}: {
  isDarkMode: boolean;
  selectedModel?: string;
  onOpenModelSettings?: () => void;
  isControlPanelOpen?: boolean;
  onOpenPanel?: () => void;
}) {
  const { t } = useTranslation();
  const messages = useSpiderChatStore((s) => s.messages);
  const isGenerating = useSpiderChatStore((s) => s.isGenerating);
  const generatingSessionId = useSpiderChatStore((s) => s.generatingSessionId);
  const isLoadingHistory = useSpiderChatStore((s) => s.isLoadingHistory);
  const currentSessionId = useSpiderChatStore((s) => s.currentSessionId);
  const targetUrl = useSpiderChatStore((s) => s.targetUrl);
  const cookies = useSpiderChatStore((s) => s.cookies);
  const rememberCookies = useSpiderChatStore((s) => s.rememberCookies);
  const setTargetUrl = useSpiderChatStore((s) => s.setTargetUrl);
  const setCookies = useSpiderChatStore((s) => s.setCookies);
  const setRememberCookies = useSpiderChatStore((s) => s.setRememberCookies);
  const restoreInterruptedHint = useSpiderChatStore((s) => s.restoreInterruptedHint);
  const setRestoreInterruptedHint = useSpiderChatStore((s) => s.setRestoreInterruptedHint);
  const isViewingLiveRun =
    isGenerating && (!generatingSessionId || generatingSessionId === currentSessionId);

  useSpiderSessionRoute();
  const { refreshWorkspace } = useSpiderWorkspace();

  const {
    sendMessage,
    resumeTask,
    resumeActiveGeneration,
    cancelCurrentRequest,
  } = useSpiderChat();
  useSpiderSessionRestore(resumeActiveGeneration);
  const [inputValue, setInputValue] = useState('');
  const [resumeDismissed, setResumeDismissed] = useState(false);

  useEffect(() => {
    setResumeDismissed(false);
  }, [currentSessionId]);

  const resumableMessage = useMemo(() => findResumableMessage(messages), [messages]);
  const canResume = Boolean(resumableMessage) && !isGenerating && !resumeDismissed;

  const { scrollContainerRef, scrollSentinelRef, showJumpButton, scrollToBottom } = useChatAutoScroll({
    deps: [messages, isViewingLiveRun],
    active: messages.length > 0,
    resetKey: currentSessionId,
  });

  useEffect(() => {
    if (currentSessionId) {
      void refreshWorkspace();
    }
  }, [currentSessionId, refreshWorkspace]);

  const inputPlaceholder = useMemo(() => t('spider.chat.placeholder'), [t]);

  const exampleUrl = 'https://movie.douban.com/top250';

  const handleSendPayload = async (text: string) => {
    if (!text || isGenerating) return;
    try {
      await sendMessage(text);
    } catch (error) {
      console.error(error);
      toast.error(error instanceof Error ? error.message : t('spider.chat.streamError'));
    }
  };

  const handleResume = async () => {
    if (isGenerating) return;
    try {
      await resumeTask();
    } catch (error) {
      console.error(error);
      toast.error(error instanceof Error ? error.message : t('spider.chat.streamError'));
    }
  };

  const emptyState = (
    <SpiderEmptyState
      prompts={[
        {
          id: 's1',
          title: t('spider.chat.suggestion1Title'),
          urlHint: exampleUrl,
          onSelect: () => {
            setTargetUrl(exampleUrl);
            setInputValue(t('spider.chat.suggestion1Prompt'));
          },
        },
        {
          id: 's2',
          title: t('spider.chat.suggestion2Title'),
          onSelect: () => setInputValue(t('spider.chat.suggestion2Prompt')),
        },
        {
          id: 's3',
          title: t('spider.chat.suggestion3Title'),
          onSelect: () => setInputValue(t('spider.chat.suggestion3Prompt')),
        },
      ]}
    />
  );

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="px-3 sm:px-4 py-2 border-b border-[var(--border-color)] bg-[var(--bg-subtle)]/60 space-y-2">
        <div>
          <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1">
            {t('spider.chat.targetUrl')}
          </label>
          <input
            type="url"
            value={targetUrl}
            onChange={(event) => setTargetUrl(event.target.value)}
            placeholder={t('spider.chat.targetUrlPlaceholder')}
            className="w-full h-9 rounded-lg border border-[var(--border-color)] bg-[var(--bg-main)] px-3 text-sm outline-none focus:ring-2 focus:ring-indigo-500/30"
          />
        </div>
        <details className="group">
          <summary className="cursor-pointer text-xs font-medium text-[var(--text-secondary)] select-none">
            {t('spider.chat.cookiesLabel')}
          </summary>
          <div className="mt-2 space-y-2">
            <textarea
              value={cookies}
              onChange={(event) => setCookies(event.target.value)}
              placeholder={t('spider.chat.cookiesPlaceholder')}
              rows={3}
              className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-main)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500/30 font-mono"
            />
            <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={rememberCookies}
                onChange={(event) => setRememberCookies(event.target.checked)}
                className="rounded border-[var(--border-color)]"
              />
              {t('spider.chat.rememberCookies')}
            </label>
            <p className="text-[11px] leading-relaxed text-[var(--text-secondary)]">
              {t('spider.chat.cookiesHint')}
            </p>
          </div>
        </details>
      </div>

      {canResume ? (
        <div className="flex items-start justify-between gap-3 border-b border-sky-500/20 bg-sky-500/10 px-3 py-2 sm:px-4">
          <div className="flex min-w-0 items-start gap-2 text-xs text-sky-800 dark:text-sky-200">
            <AlertCircle size={14} className="mt-0.5 shrink-0" />
            <span className="min-w-0 flex-1 break-words">
              {restoreInterruptedHint
                ? t('spider.chat.restoreInterrupted')
                : t('spider.chat.resumeAvailable')}
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <button
              type="button"
              className="shrink-0 rounded-md bg-sky-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-sky-500 disabled:opacity-50"
              onClick={handleResume}
              disabled={isGenerating}
            >
              {t('spider.chat.resumeTask')}
            </button>
            <button
              type="button"
              className="shrink-0 text-[11px] font-medium text-sky-700 underline-offset-2 hover:underline dark:text-sky-200"
              onClick={() => {
                setRestoreInterruptedHint(false);
                setResumeDismissed(true);
              }}
            >
              {t('common.dismiss', { defaultValue: '知道了' })}
            </button>
          </div>
        </div>
      ) : null}

      <div ref={scrollContainerRef} className="flex-1 min-h-0 overflow-y-auto">
        {isLoadingHistory ? (
          <div className="flex items-center justify-center h-full text-sm text-[var(--text-secondary)]">
            {t('common.loading')}
          </div>
        ) : messages.length === 0 ? (
          emptyState
        ) : (
          <StudioChatMessageList
            messages={messages}
            isDarkMode={isDarkMode}
            scrollSentinelRef={scrollSentinelRef}
            renderFailure={(message) =>
              message.failure ? (
                <SpiderFailureCard failure={message.failure} isDarkMode={isDarkMode} />
              ) : null
            }
          />
        )}
        {messages.length === 0 ? <div ref={scrollSentinelRef} className="h-px" /> : null}
      </div>

      {showJumpButton ? <ChatJumpToBottom onClick={() => scrollToBottom('smooth')} /> : null}

      <div className="w-full mx-auto px-3 sm:px-4 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2 shrink-0 bg-gradient-to-t from-[var(--bg-main)] via-[var(--bg-main)] to-transparent relative z-20">
        <div className="max-w-4xl mx-auto space-y-2">
          {!targetUrl.trim() && messages.length === 0 ? (
            <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <span>{t('spider.chat.urlHint')}</span>
            </div>
          ) : null}

          <QueuedChatInput
            layout="travel"
            value={inputValue}
            onChange={setInputValue}
            isBusy={isGenerating}
            onStop={isViewingLiveRun ? cancelCurrentRequest : undefined}
            getPayload={(value) => value.trim() || null}
            onSendPayload={handleSendPayload}
            getQueuedLabel={(payload) => payload}
            onQueuedEdit={(payload) => setInputValue(payload)}
            placeholder={inputPlaceholder}
            innerClassName="flex flex-col relative w-full shadow-sm bg-white dark:bg-[#1E293B] border border-slate-300 dark:border-slate-700 rounded-2xl focus-within:ring-2 focus-within:ring-indigo-500/40 focus-within:border-indigo-500 transition-all overflow-hidden"
            textareaRows={2}
          />
        </div>
      </div>
    </div>
  );
}
