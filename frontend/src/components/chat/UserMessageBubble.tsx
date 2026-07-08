import { cn } from '@/components/ui/utils';

type UserMessageBubbleProps = {
  content?: string;
  children?: React.ReactNode;
  variant?: 'travel' | 'studio';
  className?: string;
};

const bubbleVariantClasses = {
  travel:
    'max-w-[90%] sm:max-w-[85%] md:max-w-[65%] text-[15px] leading-relaxed bg-slate-100 dark:bg-[#2A2B32] text-slate-900 dark:text-slate-100 px-4 sm:px-5 py-3 sm:py-3.5 rounded-3xl',
  studio:
    'bg-[var(--bg-card)] text-[var(--text-primary)] px-3 sm:px-4 py-2.5 sm:py-3 rounded-2xl rounded-tr-sm max-w-[90%] sm:max-w-[80%] leading-relaxed border border-[var(--border-color)]',
};

function renderTravelContent(content: string) {
  return content.split('\n').map((line, index, lines) => (
    <span key={index}>
      {line}
      {index !== lines.length - 1 && <div className="h-3" />}
    </span>
  ));
}

export function UserMessageBubble({
  content,
  children,
  variant = 'travel',
  className,
}: UserMessageBubbleProps) {
  const body =
    children ??
    (content
      ? variant === 'travel'
        ? renderTravelContent(content)
        : <p className="whitespace-pre-wrap">{content}</p>
      : null);

  return (
    <div className={cn('flex w-full justify-end mb-4', className)}>
      <div className={bubbleVariantClasses[variant]}>{body}</div>
    </div>
  );
}
