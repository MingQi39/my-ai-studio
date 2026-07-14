import { Loader2, FileText } from 'lucide-react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/button';
import { cn } from '@/components/ui/utils';
import type { KnowledgeFilePreviewKind } from '@/features/spider/components/file-preview/knowledge-preview';
import { FilePreviewMonaco } from '@/features/spider/components/file-preview/file-preview-monaco';

export type FilePreviewViewerProps = {
  title: string;
  fileName?: string;
  previewDescription?: string;
  loading: boolean;
  error: string | null;
  kind: KnowledgeFilePreviewKind;
  textContent: string;
  objectUrl: string | null;
  unsupportedMessage?: string;
  onDownloadWhenUnsupported?: () => void | Promise<void>;
  isDarkMode?: boolean;
  headerActions?: ReactNode;
  className?: string;
};

export function FilePreviewViewer({
  title,
  fileName,
  previewDescription,
  loading,
  error,
  kind,
  textContent,
  objectUrl,
  unsupportedMessage,
  onDownloadWhenUnsupported,
  isDarkMode = false,
  headerActions,
  className,
}: FilePreviewViewerProps) {
  const { t } = useTranslation();
  const monacoFileName = fileName ?? title;
  const canDownload = Boolean(onDownloadWhenUnsupported) && !loading && !error;
  const useMonaco = kind === 'text' || kind === 'markdown';
  const useMonacoLayout = useMonaco || kind === 'pdf' || kind === 'image' || kind === 'html';

  return (
    <div className={cn('flex h-full min-h-0 flex-col overflow-hidden bg-[var(--bg-main)]', className)}>
      <h2 className="sr-only">{title}</h2>
      {previewDescription ? <p className="sr-only">{previewDescription}</p> : null}

      <div className="flex min-h-11 shrink-0 flex-wrap items-center gap-2 border-b border-[var(--border-color)] px-3 py-2 sm:px-4">
        <FileText className="h-3.5 w-3.5 shrink-0 text-[var(--text-secondary)]" aria-hidden />
        <div className="min-w-0 flex-[1_1_12rem] truncate text-left text-sm font-semibold leading-none">{title}</div>
        {canDownload ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 shrink-0 px-2 text-xs"
            onClick={() => void onDownloadWhenUnsupported?.()}
          >
            {t('spider.files.download', { defaultValue: '下载' })}
          </Button>
        ) : null}
        {headerActions}
      </div>

      <div
        className={cn(
          'min-h-0 flex-1',
          useMonacoLayout
            ? 'flex min-h-0 flex-1 flex-col overflow-hidden p-0'
            : 'overflow-auto bg-[var(--bg-hover)] p-3 sm:p-4',
        )}
      >
        {loading && (
          <div className="flex h-full min-h-[200px] items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-[var(--text-secondary)]" />
          </div>
        )}
        {!loading && error && <p className="p-4 text-sm text-red-500">{error}</p>}
        {!loading && !error && kind === 'unsupported' && (
          <div className="space-y-3 p-4">
            <p className="text-sm text-[var(--text-secondary)]">{unsupportedMessage}</p>
          </div>
        )}
        {!loading && !error && kind === 'text' && (
          <FilePreviewMonaco fileName={monacoFileName} value={textContent} isDarkMode={isDarkMode} />
        )}
        {!loading && !error && kind === 'markdown' && (
          <div className="h-full min-h-0 overflow-hidden">
            <FilePreviewMonaco fileName={monacoFileName} value={textContent} isDarkMode={isDarkMode} />
          </div>
        )}
        {!loading && !error && kind === 'image' && objectUrl && (
          <div className="flex min-h-0 flex-1 items-center justify-center p-4">
            <img src={objectUrl} alt="" className="max-h-full max-w-full object-contain" />
          </div>
        )}
        {!loading && !error && kind === 'pdf' && objectUrl && (
          <iframe title={title} src={objectUrl} className="h-full min-h-0 w-full flex-1 border-0" />
        )}
        {!loading && !error && kind === 'html' && objectUrl && (
          <iframe title={title} src={objectUrl} className="h-full min-h-0 w-full flex-1 border-0" />
        )}
        {!loading && !error && kind === 'office' && (
          <div className="space-y-3 p-4">
            <p className="text-sm text-[var(--text-secondary)]">{unsupportedMessage}</p>
          </div>
        )}
      </div>
    </div>
  );
}
