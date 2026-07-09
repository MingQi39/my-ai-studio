import { cn } from '@/components/ui/utils';
import { fitnessBranding } from '@/features/fitness/config/branding';
import { formatKcal } from '@/features/fitness/utils/fitnessUi';

type FitnessCalorieProgressProps = {
  goal: number;
  consumed: number;
  remaining: number;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
};

export function FitnessCalorieProgress({
  goal,
  consumed,
  remaining,
  size = 'md',
  className,
}: FitnessCalorieProgressProps) {
  const safeGoal = Math.max(goal, 1);
  const ratio = Math.min(Math.max(consumed / safeGoal, 0), 1);
  const percent = Math.round(ratio * 100);

  const dimensions = size === 'lg' ? 112 : size === 'sm' ? 64 : 88;
  const stroke = size === 'lg' ? 8 : size === 'sm' ? 5 : 7;
  const radius = (dimensions - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - ratio);

  const overBudget = remaining < 0;

  return (
    <div className={cn('flex items-center gap-4', className)}>
      <div className="relative shrink-0" style={{ width: dimensions, height: dimensions }}>
        <svg width={dimensions} height={dimensions} className="-rotate-90">
          <circle
            cx={dimensions / 2}
            cy={dimensions / 2}
            r={radius}
            fill="none"
            stroke={fitnessBranding.colors.ringTrack}
            strokeWidth={stroke}
          />
          <circle
            cx={dimensions / 2}
            cy={dimensions / 2}
            r={radius}
            fill="none"
            stroke={overBudget ? '#F59E0B' : fitnessBranding.colors.primary}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-500 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className={cn(
              'font-semibold tabular-nums text-[var(--text-primary)]',
              size === 'lg' ? 'text-xl' : size === 'sm' ? 'text-sm' : 'text-lg',
            )}
          >
            {percent}%
          </span>
          {size !== 'sm' && (
            <span className="text-[10px] text-[var(--text-secondary)]">已摄入</span>
          )}
        </div>
      </div>

      <div className="flex-1 min-w-0 space-y-2">
        <div className="h-2 rounded-full bg-[var(--bg-hover)] overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all duration-500',
              overBudget ? 'bg-amber-500' : 'bg-emerald-500',
            )}
            style={{ width: `${Math.min(percent, 100)}%` }}
          />
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <div className="text-[10px] text-[var(--text-secondary)]">目标</div>
            <div className="text-sm font-semibold tabular-nums">{formatKcal(goal)}</div>
          </div>
          <div>
            <div className="text-[10px] text-[var(--text-secondary)]">已摄入</div>
            <div className="text-sm font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
              {formatKcal(consumed)}
            </div>
          </div>
          <div>
            <div className="text-[10px] text-[var(--text-secondary)]">剩余</div>
            <div
              className={cn(
                'text-sm font-semibold tabular-nums',
                overBudget ? 'text-amber-600 dark:text-amber-400' : 'text-[var(--text-primary)]',
              )}
            >
              {formatKcal(remaining)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
