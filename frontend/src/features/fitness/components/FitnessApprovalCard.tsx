import { ShieldCheck, Trash2, Target, UtensilsCrossed } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/components/ui/utils';
import { FitnessSourceBadge } from '@/features/fitness/components/FitnessSourceBadge';
import { fitnessBranding } from '@/features/fitness/config/branding';
import type { FitnessApprovalPreview, FitnessPendingApproval } from '@/features/fitness/types/hitl';
import { formatKcal } from '@/features/fitness/utils/fitnessUi';

type FitnessApprovalCardProps = {
  approval: FitnessPendingApproval;
  disabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  className?: string;
};

function PreviewIcon({ preview }: { preview: FitnessApprovalPreview }) {
  if (preview.kind === 'log_meal') {
    return <UtensilsCrossed size={16} className="text-emerald-600 dark:text-emerald-400" />;
  }
  if (preview.kind === 'set_goal') {
    return <Target size={16} className="text-emerald-600 dark:text-emerald-400" />;
  }
  if (preview.kind === 'delete_entry') {
    return <Trash2 size={16} className="text-red-500" />;
  }
  return <ShieldCheck size={16} className="text-emerald-600 dark:text-emerald-400" />;
}

export function FitnessApprovalCard({
  approval,
  disabled,
  onConfirm,
  onCancel,
  className,
}: FitnessApprovalCardProps) {
  const { t } = useTranslation();
  const { preview } = approval;

  const title =
    preview.kind === 'log_meal'
      ? t('fitness.hitl.logMealTitle')
      : preview.kind === 'set_goal'
        ? t('fitness.hitl.setGoalTitle')
        : preview.kind === 'delete_entry'
          ? t('fitness.hitl.deleteEntryTitle')
          : t('fitness.hitl.genericTitle');

  return (
    <section className={cn('w-full max-w-4xl mx-auto px-4 pt-2 pb-4', className)}>
      <div
        className="rounded-2xl border-2 border-amber-400/80 dark:border-amber-500/50 bg-amber-50 dark:bg-amber-950/40 p-4 shadow-lg ring-2 ring-amber-400/20"
      >
        <div className="flex items-start gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
            style={{ backgroundColor: fitnessBranding.colors.primaryMuted }}
          >
            <PreviewIcon preview={preview} />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">{t('fitness.hitl.subtitle')}</p>

            {preview.kind === 'set_goal' && (
              <div className="mt-3 text-sm text-[var(--text-primary)]">
                {preview.previous_daily_calorie_goal != null &&
                preview.previous_daily_calorie_goal !== preview.daily_calorie_goal ? (
                  <p>
                    {t('fitness.hitl.goalChange', {
                      from: formatKcal(preview.previous_daily_calorie_goal),
                      to: formatKcal(preview.daily_calorie_goal),
                    })}
                  </p>
                ) : (
                  <p>{t('fitness.hitl.goalSet', { goal: formatKcal(preview.daily_calorie_goal) })}</p>
                )}
              </div>
            )}

            {preview.kind === 'log_meal' && (
              <div className="mt-3 space-y-2">
                <p className="text-xs font-medium text-[var(--text-secondary)]">
                  {t(`fitness.meal.${preview.meal_type}`, { defaultValue: preview.meal_type })}
                  {' · '}
                  {t('fitness.hitl.totalKcal', { kcal: formatKcal(preview.total_kcal) })}
                </p>
                <ul className="space-y-1.5">
                  {preview.items.map((item) => (
                    <li key={`${item.name}-${item.kcal}`} className="flex items-center justify-between gap-2 text-xs">
                      <span className="text-[var(--text-primary)]">
                        {item.name}
                        {item.qty ? ` ${item.qty}${item.unit ?? ''}` : ''}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="tabular-nums text-[var(--text-secondary)]">{formatKcal(item.kcal)}</span>
                        {item.source ? <FitnessSourceBadge source={item.source} /> : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {preview.kind === 'delete_entry' && (
              <p className="mt-3 text-sm text-[var(--text-primary)]">
                {t('fitness.hitl.deleteEntry', { id: preview.entry_id })}
              </p>
            )}
          </div>
        </div>

        <div className="mt-4 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={disabled}
            className="px-4 py-2.5 text-xs font-semibold rounded-xl border border-[var(--border-color)] text-[var(--text-secondary)] hover:bg-[var(--bg-card)] disabled:opacity-50"
          >
            {t('fitness.hitl.cancel')}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={disabled}
            className="px-4 py-2.5 text-xs font-semibold rounded-xl text-white bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50"
          >
            {t('fitness.hitl.confirm')}
          </button>
        </div>
      </div>
    </section>
  );
}
