import * as React from 'react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/components/ui/utils';

const LINE_CLAMP_CLASS: Record<number, string> = {
  2: 'line-clamp-2',
  3: 'line-clamp-3',
  4: 'line-clamp-4',
  5: 'line-clamp-5',
  6: 'line-clamp-6',
};

export type EllipsisTooltipProps = {
  children: React.ReactNode;
  tooltip?: React.ReactNode;
  lines?: number;
  as?: 'span' | 'p' | 'div' | 'h1' | 'h2' | 'h3' | 'h4';
  className?: string;
  side?: 'top' | 'right' | 'bottom' | 'left';
};

function resolveTooltipContent(
  tooltip: React.ReactNode | undefined,
  children: React.ReactNode,
): React.ReactNode | null {
  if (tooltip != null && tooltip !== false) return tooltip;
  if (typeof children === 'string' || typeof children === 'number') {
    return String(children);
  }
  return null;
}

function measureOverflow(el: HTMLElement, lines: number): boolean {
  if (lines <= 1) return el.scrollWidth > el.clientWidth + 1;
  return el.scrollHeight > el.clientHeight + 1;
}

export function EllipsisTooltip({
  children,
  tooltip,
  lines = 1,
  as: Tag = 'span',
  className,
  side = 'top',
}: EllipsisTooltipProps) {
  const ref = React.useRef<HTMLElement | null>(null);
  const [isOverflow, setIsOverflow] = React.useState(false);
  const tooltipContent = resolveTooltipContent(tooltip, children);
  const clampClass =
    lines <= 1 ? 'truncate' : (LINE_CLAMP_CLASS[lines] ?? `line-clamp-[${lines}]`);

  const remeasure = React.useCallback(() => {
    const el = ref.current;
    if (!el) return;
    setIsOverflow(measureOverflow(el, lines));
  }, [lines]);

  React.useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    let raf = 0;
    const schedule = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(remeasure);
    };

    schedule();
    const ro = new ResizeObserver(schedule);
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [remeasure, children, lines, className, tooltipContent]);

  const node = (
    <Tag ref={ref as never} className={cn('min-w-0', clampClass, className)}>
      {children}
    </Tag>
  );

  if (!isOverflow || tooltipContent == null) {
    return node;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{node}</TooltipTrigger>
      <TooltipContent
        side={side}
        className="max-w-sm break-words whitespace-normal text-left"
      >
        {tooltipContent}
      </TooltipContent>
    </Tooltip>
  );
}
