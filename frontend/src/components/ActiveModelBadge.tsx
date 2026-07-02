import { Bot, ChevronDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/components/ui/utils';

interface ActiveModelBadgeProps {
  model: string;
  onClick?: () => void;
  className?: string;
  /** compact: input bar; default: header */
  variant?: 'default' | 'compact';
}

function parseModelDisplay(model: string): { primary: string; secondary?: string } {
  const sep = model.indexOf(' - ');
  if (sep === -1) return { primary: model };
  return {
    primary: model.slice(0, sep),
    secondary: model.slice(sep + 3),
  };
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
  const { primary, secondary } = isConfigured ? parseModelDisplay(model) : { primary: displayName };

  const content =
    variant === 'compact' ? (
      <>
        <Bot
          size={14}
          className={cn(
            'flex-shrink-0',
            isConfigured ? 'text-blue-500' : 'text-[var(--text-placeholder)]',
          )}
        />
        <span
          className={cn(
            'truncate font-medium',
            isConfigured ? 'text-[var(--text-primary)]' : 'text-[var(--text-placeholder)]',
          )}
          title={displayName}
        >
          {secondary ?? primary}
        </span>
      </>
    ) : (
      <>
        <Bot
          size={15}
          className={cn(
            'flex-shrink-0',
            isConfigured ? 'text-blue-500' : 'text-[var(--text-placeholder)]',
          )}
        />
        <span
          className={cn(
            'truncate text-sm font-medium',
            isConfigured ? 'text-[var(--text-primary)]' : 'text-[var(--text-placeholder)]',
          )}
          title={displayName}
        >
          {primary}
        </span>
        {onClick && (
          <ChevronDown
            size={14}
            className="flex-shrink-0 text-[var(--text-secondary)] opacity-70"
          />
        )}
      </>
    );

  const baseClass = cn(
    'inline-flex items-center min-w-0 transition-colors',
    variant === 'compact'
      ? 'gap-1.5 rounded-full border border-[var(--border-color)] bg-[var(--bg-hover)] px-2.5 py-1 text-[11px] max-w-[180px] sm:max-w-[220px]'
      : 'gap-1.5 rounded-md px-2 py-1.5 max-w-[200px]',
    onClick &&
      (variant === 'compact'
        ? 'cursor-pointer hover:border-blue-500/30 hover:bg-[var(--bg-card)]'
        : 'cursor-pointer text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]'),
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
