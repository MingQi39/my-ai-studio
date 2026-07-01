import { Bot } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/components/ui/utils';

interface ActiveModelBadgeProps {
  model: string;
  onClick?: () => void;
  className?: string;
  /** compact: input bar; default: header */
  variant?: 'default' | 'compact';
}

export function ActiveModelBadge({
  model,
  onClick,
  className,
  variant = 'default',
}: ActiveModelBadgeProps) {
  const { t } = useTranslation();
  const displayName = model || t('workspace.noModel');
  const isConfigured = Boolean(model);

  const content = (
    <>
      <Bot
        size={variant === 'compact' ? 14 : 13}
        className={cn(
          'flex-shrink-0',
          isConfigured ? 'text-blue-500' : 'text-[var(--text-placeholder)]',
        )}
      />
      <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] flex-shrink-0">
        {t('workspace.activeModelLabel')}
      </span>
      <span
        className={cn(
          'truncate font-mono',
          isConfigured ? 'text-[var(--text-primary)]' : 'text-[var(--text-placeholder)]',
        )}
        title={displayName}
      >
        {displayName}
      </span>
    </>
  );

  const baseClass = cn(
    'inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-hover)] transition-colors max-w-[220px] min-w-0',
    variant === 'compact' ? 'px-2.5 py-1 text-[11px]' : 'px-3 py-1.5 text-xs',
    onClick && 'cursor-pointer hover:border-blue-500/40 hover:bg-[var(--bg-card)]',
    className,
  );

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={baseClass} title={t('workspace.changeModel')}>
        {content}
      </button>
    );
  }

  return <div className={baseClass}>{content}</div>;
}
