import { AlertTriangle, Lightbulb, Wrench } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import type { SpiderFailureInfo } from '@/hooks/studioChat/types';

const STAGE_I18N: Record<string, string> = {
  web_analyzer: 'spider.failure.stage.web_analyzer',
  code_generator: 'spider.failure.stage.code_generator',
  debug_agent: 'spider.failure.stage.debug_agent',
  data_processor: 'spider.failure.stage.data_processor',
};

export function SpiderFailureCard({
  failure,
  isDarkMode = false,
}: {
  failure: SpiderFailureInfo;
  isDarkMode?: boolean;
}) {
  const { t } = useTranslation();
  const stageKey = failure.stage ? STAGE_I18N[failure.stage] : undefined;
  const stageLabel = stageKey ? t(stageKey) : failure.stage;

  return (
    <div
      className={[
        'rounded-xl border px-4 py-3 space-y-3',
        isDarkMode
          ? 'border-rose-500/35 bg-rose-500/10 text-rose-100'
          : 'border-rose-300/80 bg-rose-50 text-rose-950',
      ].join(' ')}
      role="alert"
    >
      <div className="flex items-start gap-2.5">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-rose-500" />
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-semibold leading-snug">{failure.title}</p>
          {stageLabel ? (
            <p className="text-[11px] uppercase tracking-wide opacity-70">
              {t('spider.failure.stageLabel', { stage: stageLabel })}
            </p>
          ) : null}
        </div>
      </div>

      {failure.detail ? (
        <div className="flex items-start gap-2.5 text-sm leading-relaxed opacity-90">
          <Wrench className="mt-0.5 size-3.5 shrink-0 opacity-70" />
          <p className="whitespace-pre-wrap break-words">{failure.detail}</p>
        </div>
      ) : null}

      {failure.hints && failure.hints.length > 0 ? (
        <div className="rounded-lg border border-current/10 bg-black/5 dark:bg-white/5 px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-xs font-medium mb-1.5 opacity-80">
            <Lightbulb className="size-3.5" />
            {t('spider.failure.hintsTitle')}
          </div>
          <ul className="space-y-1 pl-1 text-sm leading-relaxed">
            {failure.hints.map((hint) => (
              <li key={hint} className="flex gap-2">
                <span className="opacity-50">•</span>
                <span>{hint}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {failure.recoverable ? (
        <p className="text-xs opacity-75">{t('spider.failure.recoverableHint')}</p>
      ) : null}
    </div>
  );
}
