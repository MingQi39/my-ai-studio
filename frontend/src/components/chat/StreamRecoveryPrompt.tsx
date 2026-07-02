import { RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { cn } from '@/components/ui/utils';

type StreamRecoveryPromptProps = {
  onRetry: () => void;
  isRetrying?: boolean;
  isDarkMode?: boolean;
};

export function StreamRecoveryPrompt({
  onRetry,
  isRetrying = false,
  isDarkMode = false,
}: StreamRecoveryPromptProps) {
  const { t } = useTranslation();

  return (
    <div
      className={cn(
        'rounded-2xl border px-4 py-3 text-sm leading-relaxed',
        isDarkMode
          ? 'border-white/10 bg-white/5 text-[var(--text-secondary)]'
          : 'border-[var(--border-color)] bg-[var(--bg-hover)]/60 text-[var(--text-secondary)]',
      )}
    >
      <p className="whitespace-pre-wrap">{t('workspace.streamRecoveryMessage')}</p>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={onRetry}
        disabled={isRetrying}
        className="mt-3 gap-2"
      >
        <RefreshCw className={cn('h-3.5 w-3.5', isRetrying && 'animate-spin')} />
        {isRetrying ? t('workspace.streamRecoveryRetrying') : t('workspace.streamRecoveryRetry')}
      </Button>
    </div>
  );
}
