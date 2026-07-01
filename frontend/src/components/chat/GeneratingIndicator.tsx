import { Loader2 } from 'lucide-react';
import { cn } from '@/components/ui/utils';

const DOT_DELAYS_SM = ['0s', '0.15s', '0.3s'] as const;
const DOT_DELAYS_MD = ['0s', '0.2s', '0.4s'] as const;

type GeneratingIndicatorProps = {
  layout?: 'avatar' | 'dots' | 'spinner';
  label?: string;
  icon?: React.ReactNode;
  dotClassName?: string;
  dotSize?: 'sm' | 'md';
  className?: string;
};

function BouncingDots({
  dotClassName,
  dotSize = 'md',
  className,
}: {
  dotClassName: string;
  dotSize?: 'sm' | 'md';
  className?: string;
}) {
  const sizeClass = dotSize === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2';
  const delays = dotSize === 'sm' ? DOT_DELAYS_SM : DOT_DELAYS_MD;

  return (
    <span className={cn('flex items-center gap-1', className)}>
      {delays.map((delay, index) => (
        <span
          key={index}
          className={cn(sizeClass, 'rounded-full animate-bounce', dotClassName)}
          style={{ animationDelay: delay }}
        />
      ))}
    </span>
  );
}

export function GeneratingIndicator({
  layout = 'avatar',
  label,
  icon,
  dotClassName = 'bg-[#3B82F6]',
  dotSize = 'md',
  className,
}: GeneratingIndicatorProps) {
  if (layout === 'spinner') {
    return (
      <div className={cn('flex items-center gap-2 text-[var(--text-secondary)]', className)}>
        <Loader2 size={16} className="animate-spin" />
        {label && <span className="text-sm">{label}</span>}
      </div>
    );
  }

  if (layout === 'dots') {
    return <BouncingDots dotClassName={dotClassName} dotSize={dotSize} className={className} />;
  }

  return (
    <div className={cn('flex w-full justify-start mb-6', className)}>
      {icon && (
        <div className="w-8 h-8 rounded-full bg-[#3B82F6] flex items-center justify-center text-white mr-4 flex-shrink-0 mt-0.5 shadow-sm">
          {icon}
        </div>
      )}
      <div className="py-2.5 flex items-center">
        <BouncingDots dotClassName={dotClassName} dotSize={dotSize} />
      </div>
    </div>
  );
}
