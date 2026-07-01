import { cn } from '@/components/ui/utils';

type AssistantMessageShellProps = {
  layout?: 'travel' | 'studio';
  showAvatar?: boolean;
  avatar?: React.ReactNode;
  bodyClassName?: string;
  className?: string;
  footer?: React.ReactNode;
  children: React.ReactNode;
};

export function AssistantMessageShell({
  layout = 'travel',
  showAvatar = true,
  avatar,
  bodyClassName,
  className,
  footer,
  children,
}: AssistantMessageShellProps) {
  if (layout === 'studio') {
    return <div className={cn('flex flex-col gap-6', className)}>{children}</div>;
  }

  return (
    <div className={cn('flex w-full justify-start group', className)}>
      {showAvatar && avatar && (
        <div className="w-8 h-8 rounded-full bg-[#3B82F6] flex items-center justify-center text-white mr-4 flex-shrink-0 shadow-sm mt-0.5">
          {avatar}
        </div>
      )}

      <div className={cn('flex flex-col items-start', bodyClassName ?? 'max-w-[80%]')}>
        {children}
        {footer}
      </div>
    </div>
  );
}
