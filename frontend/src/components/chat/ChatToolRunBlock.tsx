import { useTranslation } from 'react-i18next';
import { Code, Globe, Loader2 } from 'lucide-react';
import { cn } from '@/components/ui/utils';

export type ChatToolRun = {
  call_id?: string;
  tool_name: string;
  raw_tool_name?: string;
  tool_type?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: string;
  status: 'running' | 'completed' | 'error';
};

type ChatToolRunBlockProps = {
  run: ChatToolRun;
  isDarkMode?: boolean;
};

export function ChatToolRunBlock({ run, isDarkMode = false }: ChatToolRunBlockProps) {
  const { t } = useTranslation();
  const isRunning = run.status === 'running';
  const isError = run.status === 'error';
  const label =
    run.tool_name === 'web_search'
      ? t('controlPanel.googleSearch')
      : run.tool_name === 'calculate'
        ? t('controlPanel.functionCall')
        : run.tool_name;

  return (
    <div className="rounded-lg border border-[var(--border-color)] overflow-hidden text-sm">
      <div className="flex items-center justify-between px-4 py-2 bg-[var(--bg-card)] border-b border-[var(--border-color)]">
        <div className="flex items-center gap-2">
          {run.tool_name === 'web_search' ? (
            <Globe size={14} className="text-blue-400" />
          ) : (
            <Code size={14} className="text-emerald-400" />
          )}
          <span className="font-medium text-[var(--text-primary)]">{label}</span>
        </div>
        {isRunning && <Loader2 size={14} className="animate-spin text-blue-400" />}
        {isError && <span className="text-xs text-red-500">{t('workspace.toolFailed')}</span>}
      </div>
      {run.tool_input && Object.keys(run.tool_input).length > 0 && (
        <pre className="px-4 py-2 text-xs font-mono text-[var(--text-secondary)] border-b border-[var(--border-color)] overflow-x-auto">
          {JSON.stringify(run.tool_input, null, 2)}
        </pre>
      )}
      {run.tool_output && (
        <pre
          className={cn(
            'px-4 py-3 text-xs font-mono overflow-x-auto max-h-48 overflow-y-auto',
            isDarkMode ? 'bg-[#0F172A] text-slate-300' : 'bg-slate-50 text-slate-700',
          )}
        >
          {run.tool_output}
        </pre>
      )}
    </div>
  );
}
