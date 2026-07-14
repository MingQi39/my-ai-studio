import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Coffee,
  Cookie,
  Loader2,
  Moon,
  RefreshCw,
  Sun,
  Trash2,
  X,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { EllipsisTooltip } from '@/components/EllipsisTooltip';
import { Input } from '@/components/ui/input';
import { cn } from '@/components/ui/utils';

import { FitnessCalorieProgress } from '@/features/fitness/components/FitnessCalorieProgress';
import { FitnessSourceBadge } from '@/features/fitness/components/FitnessSourceBadge';
import { fitnessBranding } from '@/features/fitness/config/branding';
import { useFitnessTodaySummary } from '@/features/fitness/hooks/useFitnessTodaySummary';
import { updateDailyCalorieGoal, deleteFitnessDiaryEntry } from '@/features/fitness/services/api/fitness';
import { formatKcal, mealTypeKey } from '@/features/fitness/utils/fitnessUi';

interface FitnessControlPanelProps {
  selectedModel: string;
  onOpenModelSettings: () => void;
  isOpen: boolean;
  onClose?: () => void;
}

const MEAL_ICONS = {
  breakfast: Sun,
  lunch: Coffee,
  dinner: Moon,
  snack: Cookie,
  other: Cookie,
} as const;

export function FitnessControlPanel({ isOpen, onClose }: FitnessControlPanelProps) {
  const { t } = useTranslation();
  const { todaySummary, refresh } = useFitnessTodaySummary(isOpen);
  const [saving, setSaving] = useState(false);
  const [goalDraft, setGoalDraft] = useState<number>(1800);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (todaySummary?.daily_calorie_goal) {
      setGoalDraft(todaySummary.daily_calorie_goal);
    }
  }, [todaySummary?.daily_calorie_goal]);

  const onSaveGoal = async () => {
    setSaving(true);
    try {
      await updateDailyCalorieGoal(goalDraft);
      await refresh();
      toast.success(t('fitness.panel.saved'));
    } catch {
      toast.error(t('fitness.panel.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const onDeleteEntry = async (entryId: string) => {
    setSaving(true);
    try {
      await deleteFitnessDiaryEntry(entryId);
      await refresh();
      toast.success(t('fitness.panel.deleted'));
    } catch {
      toast.error(t('fitness.panel.deleteFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await refresh();
    setRefreshing(false);
  };

  if (!isOpen) return null;

  const consumed = todaySummary?.consumed_kcal ?? 0;
  const remaining = todaySummary?.remaining_kcal ?? 0;
  const goal = todaySummary?.daily_calorie_goal ?? goalDraft;

  return (
    <div
      className="w-full md:w-[320px] h-full flex flex-col border-l border-[var(--border-color)]"
      style={{ backgroundColor: 'var(--bg-panel)' }}
    >
      <div className="p-4 border-b border-[var(--border-color)] flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">{t('fitness.panel.title')}</h2>
          <p className="text-xs text-[var(--text-secondary)] mt-1">{t('fitness.panel.subtitle')}</p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => void handleRefresh()}
            disabled={refreshing || saving}
            aria-label={t('fitness.panel.refresh')}
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          </Button>
          {onClose && (
            <Button variant="ghost" size="icon" className="h-8 w-8 md:hidden" onClick={onClose}>
              <X size={16} />
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        <section className="rounded-2xl border border-[var(--border-color)] p-4 space-y-4 bg-[var(--bg-card)]">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-semibold text-[var(--text-primary)]">{t('fitness.panel.goal')}</div>
            <span className="text-[11px] px-2 py-1 rounded-lg bg-[var(--bg-hover)] text-[var(--text-secondary)]">
              {todaySummary?.date ?? '—'}
            </span>
          </div>

          {todaySummary ? (
            <FitnessCalorieProgress
              goal={goal}
              consumed={consumed}
              remaining={remaining}
              size="md"
            />
          ) : (
            <div className="h-24 rounded-xl bg-[var(--bg-hover)] animate-pulse" />
          )}

          <div className="flex items-center gap-2">
            <Input
              type="number"
              value={goalDraft}
              min={800}
              max={10000}
              onChange={(e) => setGoalDraft(Number(e.target.value))}
              disabled={saving}
              className="w-full"
            />
            <Button
              onClick={onSaveGoal}
              disabled={saving}
              className="shrink-0 bg-emerald-600 hover:bg-emerald-700"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : t('fitness.panel.save')}
            </Button>
          </div>
        </section>

        <section className="rounded-2xl border border-[var(--border-color)] p-4 space-y-3 bg-[var(--bg-card)]">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-[var(--text-primary)]">{t('fitness.panel.entries')}</div>
            <span className="text-[11px] text-[var(--text-secondary)]">
              {todaySummary?.entries?.length ?? 0}
            </span>
          </div>

          {!todaySummary && (
            <div className="space-y-2">
              <div className="h-16 rounded-xl bg-[var(--bg-hover)] animate-pulse" />
              <div className="h-16 rounded-xl bg-[var(--bg-hover)] animate-pulse" />
            </div>
          )}

          {todaySummary && todaySummary.entries.length === 0 && (
            <div className="rounded-xl border border-dashed border-[var(--border-color)] p-6 text-center">
              <p className="text-sm text-[var(--text-secondary)]">{t('fitness.panel.noEntries')}</p>
              <p className="text-xs text-[var(--text-secondary)] mt-1">{t('fitness.panel.noEntriesHint')}</p>
            </div>
          )}

          {todaySummary?.entries.map((entry) => {
            const mealKey = mealTypeKey(entry.meal_type);
            const MealIcon = MEAL_ICONS[mealKey as keyof typeof MEAL_ICONS] ?? MEAL_ICONS.other;

            return (
              <div
                key={entry.id}
                className="rounded-xl border border-[var(--border-color)] p-3 space-y-2 hover:border-emerald-500/20 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                      style={{ backgroundColor: fitnessBranding.colors.primaryMuted }}
                    >
                      <MealIcon size={14} className="text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-[var(--text-primary)]">
                        {t(`fitness.meal.${mealKey}`, entry.meal_type)}
                      </div>
                      <div className="text-[11px] text-[var(--text-secondary)]">
                        {t('fitness.panel.total')}: {formatKcal(entry.total_kcal)} kcal
                      </div>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-500/10"
                    disabled={saving}
                    onClick={() => onDeleteEntry(entry.id)}
                    aria-label={t('fitness.panel.deleteEntry')}
                  >
                    <Trash2 size={15} />
                  </Button>
                </div>

                <div className="space-y-2 pl-10">
                  {entry.items.map((it, idx) => (
                    <div
                      key={`${entry.id}-${idx}`}
                      className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-2 gap-y-1 text-xs"
                    >
                      <span className="text-[var(--text-primary)] leading-snug break-words whitespace-normal">
                        <EllipsisTooltip lines={2}>{it.name}</EllipsisTooltip>{' '}
                        <span className="text-[var(--text-secondary)] whitespace-nowrap">
                          {it.qty}
                          {it.unit}
                        </span>
                      </span>
                      <div className="flex flex-col items-end gap-1 sm:flex-row sm:items-center sm:gap-1.5 shrink-0">
                        <span className="tabular-nums text-[var(--text-secondary)] leading-5">
                          {formatKcal(it.kcal)}
                        </span>
                        <FitnessSourceBadge source={it.source} />
                      </div>
                    </div>
                  ))}
                </div>

                {entry.note && (
                  <p className="text-[11px] text-[var(--text-secondary)] pl-10 italic">{entry.note}</p>
                )}
              </div>
            );
          })}
        </section>

        <div
          className={cn(
            'rounded-xl border p-3 flex gap-2 text-[11px] leading-relaxed',
            'border-amber-500/20 bg-amber-500/5 text-amber-900 dark:text-amber-100',
          )}
        >
          <AlertCircle size={14} className="shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
          <p>{todaySummary?.disclaimer ?? t('fitness.disclaimer')}</p>
        </div>
      </div>
    </div>
  );
}
