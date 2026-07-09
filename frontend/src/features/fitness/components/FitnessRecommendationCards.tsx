import { Sparkles, UtensilsCrossed } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/components/ui/utils';
import { FitnessSourceBadge } from '@/features/fitness/components/FitnessSourceBadge';
import { fitnessBranding } from '@/features/fitness/config/branding';
import { formatKcal } from '@/features/fitness/utils/fitnessUi';

export type FitnessRecommendation = {
  id: string;
  title: string;
  items: Array<{ name: string; qty: number; unit: string; kcal: number; source: string }>;
  total_kcal: number;
  notes?: string | null;
};

type FitnessRecommendationCardsProps = {
  recommendations: FitnessRecommendation[];
  disabled?: boolean;
  onConfirm: (index: number) => void;
  className?: string;
};

export function FitnessRecommendationCards({
  recommendations,
  disabled,
  onConfirm,
  className,
}: FitnessRecommendationCardsProps) {
  const { t } = useTranslation();

  if (!recommendations.length) return null;

  return (
    <section className={cn('w-full max-w-4xl mx-auto px-4 pt-2 pb-4', className)}>
      <div className="flex items-center gap-2 mb-3">
        <div
          className="w-8 h-8 rounded-xl flex items-center justify-center"
          style={{ backgroundColor: fitnessBranding.colors.primaryMuted }}
        >
          <UtensilsCrossed size={16} className="text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            {t('fitness.chat.recommendations')}
          </h3>
          <p className="text-xs text-[var(--text-secondary)]">{t('fitness.chat.recommendationsHint')}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {recommendations.map((rec, idx) => (
          <article
            key={rec.id}
            className="group relative rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] p-4 shadow-sm hover:shadow-md hover:border-emerald-500/30 transition-all duration-200"
          >
            <div className="absolute top-3 right-3 w-7 h-7 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-bold flex items-center justify-center">
              {idx + 1}
            </div>

            <div className="pr-8">
              <h4 className="text-sm font-semibold text-[var(--text-primary)] truncate">{rec.title}</h4>
              <p className="mt-1 text-xs text-[var(--text-secondary)] flex items-center gap-1">
                <Sparkles size={12} className="text-emerald-500" />
                {t('fitness.chat.totalKcal', { kcal: formatKcal(rec.total_kcal) })}
              </p>
            </div>

            <ul className="mt-3 space-y-2">
              {rec.items.map((item) => (
                <li
                  key={`${rec.id}-${item.name}`}
                  className="flex items-start justify-between gap-2 text-xs"
                >
                  <div className="min-w-0">
                    <span className="text-[var(--text-primary)] font-medium">{item.name}</span>
                    <span className="text-[var(--text-secondary)] ml-1">
                      {item.qty}
                      {item.unit}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className="tabular-nums text-[var(--text-secondary)]">
                      {formatKcal(item.kcal)}
                    </span>
                    <FitnessSourceBadge source={item.source} />
                  </div>
                </li>
              ))}
            </ul>

            {rec.notes && (
              <p className="mt-2 text-[11px] text-[var(--text-secondary)] leading-relaxed">{rec.notes}</p>
            )}

            <button
              type="button"
              onClick={() => onConfirm(idx)}
              disabled={disabled}
              className="mt-4 w-full px-3 py-2.5 text-xs font-semibold rounded-xl text-white bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {t('fitness.chat.confirmMeal', { index: idx + 1 })}
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
