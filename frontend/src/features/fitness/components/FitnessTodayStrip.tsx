import { ChevronRight, Flame } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/components/ui/utils';
import type { FitnessTodaySummary } from '@/features/fitness/stores/useFitnessChatStore';
import { formatKcal } from '@/features/fitness/utils/fitnessUi';
import { fitnessBranding } from '@/features/fitness/config/branding';

type FitnessTodayStripProps = {
  summary: FitnessTodaySummary | null;
  loading?: boolean;
  onOpenPanel?: () => void;
  className?: string;
};

export function FitnessTodayStrip({
  summary,
  loading,
  onOpenPanel,
  className,
}: FitnessTodayStripProps) {
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className={cn('px-3 sm:px-4 py-2 border-b border-[var(--border-color)] bg-[var(--bg-card)]/60', className)}>
        <div className="max-w-4xl mx-auto h-9 rounded-lg bg-[var(--bg-hover)] animate-pulse" />
      </div>
    );
  }

  if (!summary) return null;

  const overBudget = summary.remaining_kcal < 0;
  const consumedRatio = Math.min(
    Math.max(summary.consumed_kcal / Math.max(summary.daily_calorie_goal, 1), 0),
    1,
  );

  return (
    <button
      type="button"
      onClick={onOpenPanel}
      className={cn(
        'w-full text-left px-3 sm:px-4 py-2.5 border-b border-[var(--border-color)] bg-gradient-to-r from-emerald-500/5 to-transparent hover:from-emerald-500/10 transition-colors',
        className,
      )}
    >
      <div className="max-w-4xl mx-auto flex items-center gap-3">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
          style={{ backgroundColor: fitnessBranding.colors.primaryMuted }}
        >
          <Flame size={18} className="text-emerald-600 dark:text-emerald-400" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 text-xs text-[var(--text-secondary)]">
            <span>{t('fitness.strip.today', { date: summary.date })}</span>
            <span className="hidden sm:inline">{t('fitness.strip.tapToOpen')}</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-[var(--bg-hover)] overflow-hidden">
            <div
              className={cn('h-full rounded-full transition-all', overBudget ? 'bg-amber-500' : 'bg-emerald-500')}
              style={{ width: `${Math.round(consumedRatio * 100)}%` }}
            />
          </div>
          <div className="mt-1.5 flex items-center gap-3 text-xs">
            <span>
              {t('fitness.strip.consumed')}{' '}
              <strong className="text-emerald-600 dark:text-emerald-400 tabular-nums">
                {formatKcal(summary.consumed_kcal)}
              </strong>
            </span>
            <span className="text-[var(--text-secondary)]">/</span>
            <span>
              {t('fitness.strip.goal')}{' '}
              <strong className="tabular-nums">{formatKcal(summary.daily_calorie_goal)}</strong>
            </span>
            <span className="text-[var(--text-secondary)]">·</span>
            <span>
              {t('fitness.strip.remaining')}{' '}
              <strong
                className={cn(
                  'tabular-nums',
                  overBudget ? 'text-amber-600 dark:text-amber-400' : 'text-[var(--text-primary)]',
                )}
              >
                {formatKcal(summary.remaining_kcal)}
              </strong>
            </span>
          </div>
        </div>

        <ChevronRight size={16} className="text-[var(--text-secondary)] shrink-0" />
      </div>
    </button>
  );
}
