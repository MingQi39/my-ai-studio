import { ArrowDown } from 'lucide-react';
import { cn } from '@/components/ui/utils';

type ChatJumpToBottomProps = {
  onClick: () => void;
  label?: string;
  className?: string;
};

export function ChatJumpToBottom({
  onClick,
  label = '回到底部',
  className,
}: ChatJumpToBottomProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'absolute bottom-36 right-6 z-20 flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/95 px-4 py-2 text-sm font-medium text-slate-700 shadow-lg backdrop-blur-sm transition-all hover:border-[#3B82F6] hover:text-[#3B82F6] dark:border-slate-700 dark:bg-[#1E293B]/95 dark:text-slate-200 dark:hover:border-[#3B82F6] dark:hover:text-[#3B82F6]',
        className,
      )}
      aria-label={label}
    >
      <ArrowDown size={16} />
      {label}
    </button>
  );
}
