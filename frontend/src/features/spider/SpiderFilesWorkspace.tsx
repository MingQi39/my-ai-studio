import React, { useEffect } from 'react';
import { Bug, FileCode2, FileText, FolderOpen, Menu, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { ActiveModelBadge } from '@/components/ActiveModelBadge';
import { EllipsisTooltip } from '@/components/EllipsisTooltip';
import { cn } from '@/components/ui/utils';
import { FilePreviewViewer } from '@/features/spider/components/file-preview/FilePreviewViewer';
import { SpiderSessionScopeMeta } from '@/features/spider/components/SpiderSessionScopeMeta';
import { spiderBranding } from '@/features/spider/config/branding';
import { useSpiderFilePreview } from '@/features/spider/hooks/useSpiderFilePreview';
import { useSpiderFilesSessionRoute } from '@/features/spider/hooks/useSpiderFilesSessionRoute';
import { useSpiderSessionLabel } from '@/features/spider/hooks/useSpiderSessionLabel';
import { useSpiderWorkspace } from '@/features/spider/hooks/useSpiderWorkspace';

interface SpiderFilesWorkspaceProps {
  isDarkMode: boolean;
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  selectedModel: string;
  onOpenModelSettings: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function SpiderFilesWorkspace({
  isDarkMode,
  isSidebarOpen,
  toggleSidebar,
  selectedModel,
  onOpenModelSettings,
}: SpiderFilesWorkspaceProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { currentSessionId } = useSpiderFilesSessionRoute();
  const { title: sessionTitle, targetUrl } = useSpiderSessionLabel(currentSessionId);
  const { workspaceFiles, refreshWorkspace } = useSpiderWorkspace();
  const {
    selectedFile,
    selectFile,
    previewOpen,
    previewLoading,
    previewTitle,
    previewKind,
    previewText,
    previewObjectUrl,
    previewError,
    previewOnDownloadUnsupported,
    previewDescription,
    previewUnsupportedMessage,
  } = useSpiderFilePreview(currentSessionId);

  useEffect(() => {
    if (isDarkMode) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  }, [isDarkMode]);

  useEffect(() => {
    if (currentSessionId) {
      void refreshWorkspace();
    }
  }, [currentSessionId, refreshWorkspace]);

  return (
    <div className="flex h-full w-full min-w-0 flex-col bg-[var(--bg-main)] text-[var(--text-primary)]">
      <header className="flex min-h-14 flex-shrink-0 items-center justify-between gap-3 border-b border-[var(--border-color)] bg-[var(--bg-main)]/80 px-3 py-2 backdrop-blur-sm sm:px-4">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className={cn('h-9 w-9 shrink-0', isSidebarOpen ? 'md:hidden' : '')}
          >
            <Menu size={20} />
          </Button>

          <div
            className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-xl sm:flex"
            style={{ backgroundColor: spiderBranding.colors.primaryMuted }}
          >
            <Bug size={18} className="text-indigo-600 dark:text-indigo-400" />
          </div>

          <div className="min-w-0">
            <EllipsisTooltip as="h1" className="text-sm font-semibold">
              {t('spider.files.title')}
            </EllipsisTooltip>
            {currentSessionId ? (
              <SpiderSessionScopeMeta
                sessionId={currentSessionId}
                title={sessionTitle}
                targetUrl={targetUrl}
                className="mt-0.5"
              />
            ) : (
              <EllipsisTooltip as="p" className="text-xs text-[var(--text-secondary)]">
                {t('spider.files.subtitle')}
              </EllipsisTooltip>
            )}
          </div>
        </div>

        <div className="flex flex-shrink-0 items-center gap-1 sm:gap-2">
          <ActiveModelBadge
            model={selectedModel}
            onClick={onOpenModelSettings}
            className="hidden sm:inline-flex"
          />
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden lg:flex-row">
        <aside className="flex h-[min(42dvh,360px)] min-h-[180px] w-full shrink-0 flex-col border-b border-[var(--border-color)] bg-[var(--bg-main)] lg:h-full lg:w-[300px] lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between gap-3 border-b border-[var(--border-color)] px-4 py-3">
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-1.5">
                <FolderOpen size={14} className="shrink-0 text-[var(--text-secondary)]" />
                <EllipsisTooltip as="h2" className="text-sm font-semibold">
                  {t('spider.panel.workspace')}
                </EllipsisTooltip>
              </div>
              <SpiderSessionScopeMeta
                sessionId={currentSessionId}
                title={sessionTitle}
                targetUrl={targetUrl}
                className="mt-1"
                indentClassName="pl-5"
              />
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0"
              onClick={() => void refreshWorkspace()}
              disabled={!currentSessionId}
            >
              <RefreshCw size={14} />
            </Button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {!currentSessionId ? (
              <p className="px-1 text-xs text-[var(--text-secondary)]">{t('spider.panel.noSession')}</p>
            ) : workspaceFiles.length === 0 ? (
              <p className="px-1 text-xs text-[var(--text-secondary)]">{t('spider.panel.noFiles')}</p>
            ) : (
              <ul className="space-y-2">
                {workspaceFiles.map((file) => (
                  <li key={file.name}>
                    <button
                      type="button"
                      onClick={() => selectFile(file.name)}
                      className={cn(
                        'flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left transition-colors',
                        selectedFile === file.name
                          ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30'
                          : 'border-[var(--border-color)] hover:bg-[var(--bg-hover)]',
                      )}
                    >
                      <FileCode2 size={14} className="shrink-0 text-indigo-500" />
                      <div className="min-w-0 flex-1">
                        <EllipsisTooltip as="p" className="text-sm font-medium">
                          {file.name}
                        </EllipsisTooltip>
                        <p className="text-[10px] text-[var(--text-secondary)]">
                          {formatFileSize(file.size)}
                          {file.modified_at ? ` · ${file.modified_at}` : ''}
                        </p>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        <main className="min-h-[420px] min-w-0 flex-1 lg:min-h-0">
          {previewOpen && selectedFile ? (
            <FilePreviewViewer
              title={previewTitle}
              fileName={previewTitle}
              previewDescription={previewDescription}
              loading={previewLoading}
              error={previewError}
              kind={previewKind}
              textContent={previewText}
              objectUrl={previewObjectUrl}
              unsupportedMessage={previewUnsupportedMessage}
              onDownloadWhenUnsupported={previewOnDownloadUnsupported}
              isDarkMode={isDarkMode}
              className="h-full"
            />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-sm text-[var(--text-secondary)]">
              <FileText className="h-12 w-12 opacity-30" aria-hidden />
              <p>{t('spider.files.empty')}</p>
              {!currentSessionId ? (
                <Button variant="outline" size="sm" onClick={() => navigate('/spider/chat')}>
                  {t('spider.files.goToChat')}
                </Button>
              ) : null}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
