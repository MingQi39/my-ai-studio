import React from 'react';
import { Bug, ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { cn } from '@/components/ui/utils';
import { EllipsisTooltip } from '@/components/EllipsisTooltip';
import { spiderBranding } from '@/features/spider/config/branding';

export type SpiderQuickPrompt = {
  id: string;
  title: string;
  urlHint?: string;
  onSelect: () => void;
};

interface SpiderEmptyStateProps {
  prompts: SpiderQuickPrompt[];
  className?: string;
}

export function SpiderEmptyState({ prompts, className }: SpiderEmptyStateProps) {
  const { t } = useTranslation();

  return (
    <div
      className={cn(
        'mx-auto flex w-full max-w-xl flex-col px-4 pb-8 pt-10 sm:px-6 sm:pt-14',
        'animate-in fade-in duration-500',
        className,
      )}
    >
      <div className="mb-8 text-center">
        <div
          className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl"
          style={{ backgroundColor: spiderBranding.colors.primaryMuted }}
        >
          <Bug size={22} className="text-indigo-600 dark:text-indigo-400" aria-hidden />
        </div>
        <h2 className="text-lg font-semibold tracking-tight text-[var(--text-primary)] sm:text-xl">
          {t('spider.chat.emptyTitle')}
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-[var(--text-secondary)]">
          {t('spider.chat.emptyDescription')}
        </p>
      </div>

      <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--text-secondary)]">
        {t('spider.chat.tryTasks')}
      </div>

      <ul className="divide-y divide-[var(--border-color)] overflow-hidden rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)]">
        {prompts.map((prompt, index) => (
          <li key={prompt.id}>
            <button
              type="button"
              onClick={prompt.onSelect}
              className="group flex w-full items-start gap-3 px-4 py-3.5 text-left transition-colors hover:bg-[var(--bg-hover)]"
            >
              <span
                className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-indigo-600 dark:text-indigo-300"
                style={{ backgroundColor: spiderBranding.colors.primaryMuted }}
              >
                {index + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-[var(--text-primary)] group-hover:text-indigo-600 dark:group-hover:text-indigo-300">
                  {prompt.title}
                </span>
                {prompt.urlHint ? (
                  <EllipsisTooltip className="mt-0.5 block font-mono text-[11px] text-[var(--text-secondary)]">
                    {prompt.urlHint}
                  </EllipsisTooltip>
                ) : null}
              </span>
              <ChevronRight
                size={16}
                className="mt-1 shrink-0 text-[var(--text-secondary)] opacity-0 transition-opacity group-hover:opacity-100"
              />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
