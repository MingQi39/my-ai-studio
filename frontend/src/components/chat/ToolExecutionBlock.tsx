import { useTranslation } from 'react-i18next';
import { Loader2, Terminal } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

type ToolExecutionBlockProps = {
  code: string;
  output?: string;
  status: 'running' | 'completed';
  isDarkMode?: boolean;
};

export function ToolExecutionBlock({
  code,
  output,
  status,
  isDarkMode = false,
}: ToolExecutionBlockProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col rounded-lg overflow-hidden border border-[var(--border-color)] w-full max-w-full animate-in zoom-in-95 duration-300">
      <div className="bg-[var(--bg-card)]">
        <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border-color)]">
          <div className="flex items-center gap-2">
            <Terminal size={14} className="text-[var(--text-secondary)]" />
            <span className="text-xs font-medium text-[var(--text-primary)]">{t('workspace.pythonCode')}</span>
          </div>
          <div className="flex items-center gap-3">
            {status === 'running' && (
              <div className="flex items-center gap-2 text-blue-400">
                <Loader2 size={12} className="animate-spin" />
                <span className="text-[10px] uppercase font-bold tracking-wider">{t('workspace.executing')}</span>
              </div>
            )}
            <Badge
              variant="secondary"
              className="bg-[var(--bg-hover)] text-[var(--text-secondary)] text-[10px] h-5 rounded-sm"
            >
              pandas
            </Badge>
          </div>
        </div>
        <div className="p-4 overflow-x-auto relative">
          <pre className="text-sm font-mono text-[var(--text-primary)]">{code}</pre>
          {status === 'running' && (
            <div
              className="absolute inset-0 bg-gradient-to-r from-transparent via-[var(--bg-hover)] to-transparent animate-shimmer"
              style={{ backgroundSize: '200% 100%' }}
            />
          )}
        </div>
      </div>

      {output && (
        <div
          className={`border-t border-[var(--border-color)] p-4 animate-in slide-in-from-top-2 duration-300 ${isDarkMode ? 'bg-[#000000]' : 'bg-[#1e1e1e]'}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-medium text-[#8E9196] uppercase tracking-wider">
              {t('workspace.consoleOutput')}
            </span>
          </div>
          <div className="font-mono text-xs text-green-400 whitespace-pre-wrap">{output}</div>
        </div>
      )}
    </div>
  );
}
