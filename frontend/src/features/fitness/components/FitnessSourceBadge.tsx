import { useTranslation } from 'react-i18next';
import { cn } from '@/components/ui/utils';
import { sourceStyle, type CalorieSource } from '@/features/fitness/utils/fitnessUi';

export function FitnessSourceBadge({
  source,
  className,
}: {
  source: CalorieSource;
  className?: string;
}) {
  const { t } = useTranslation();
  const style = sourceStyle(source);
  const label = t(`fitness.source.${source}`, source);

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium',
        style.className,
        className,
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', style.dotClassName)} />
      {label}
    </span>
  );
}
