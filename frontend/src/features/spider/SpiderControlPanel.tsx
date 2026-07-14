import React, { useEffect } from 'react';
import {
  AlertCircle,
  Brain,
  ChevronRight,
  FileCode2,
  FolderOpen,
  GitBranch,
  RefreshCw,
  X,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { cn } from '@/components/ui/utils';
import { spiderBranding } from '@/features/spider/config/branding';
import { SpiderSessionScopeMeta } from '@/features/spider/components/SpiderSessionScopeMeta';
import { useSpiderSessionLabel } from '@/features/spider/hooks/useSpiderSessionLabel';
import { useSpiderWorkspace } from '@/features/spider/hooks/useSpiderWorkspace';
import { useSpiderChatStore } from '@/features/spider/stores/useSpiderChatStore';

interface SpiderControlPanelProps {
  selectedModel: string;
  onOpenModelSettings: () => void;
  isOpen: boolean;
  onClose?: () => void;
}

const FLOW_STEP_KEYS = ['flowAnalyze', 'flowGenerate', 'flowExecute', 'flowClean'] as const;

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function SpiderControlPanel({ selectedModel, onOpenModelSettings, isOpen, onClose }: SpiderControlPanelProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const currentSessionId = useSpiderChatStore((s) => s.currentSessionId);
  const isGenerating = useSpiderChatStore((s) => s.isGenerating);
  const { title: sessionTitle, targetUrl } = useSpiderSessionLabel(currentSessionId);
  const { workspaceFiles, refreshWorkspace } = useSpiderWorkspace();

  useEffect(() => {
    if (isOpen && currentSessionId) {
      void refreshWorkspace();
    }
  }, [isOpen, currentSessionId, refreshWorkspace]);

  useEffect(() => {
    if (!isOpen || !currentSessionId || !isGenerating) return;
    const timer = window.setInterval(() => {
      void refreshWorkspace();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [isOpen, currentSessionId, isGenerating, refreshWorkspace]);

  if (!isOpen) return null;

  return (
    <aside
      className="flex h-full w-full min-w-0 max-w-full flex-col overflow-hidden border-l border-[var(--border-color)]"
      style={{ backgroundColor: 'var(--bg-panel)' }}
    >
      <div className="flex items-start justify-between gap-2 border-b border-[var(--border-color)] p-4">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-semibold text-[var(--text-primary)]">{t('spider.panel.title')}</h2>
          <p className="mt-1 text-xs text-[var(--text-secondary)] break-words">{t('spider.panel.subtitle')}</p>
        </div>
        {onClose ? (
          <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0 md:hidden" onClick={onClose}>
            <X size={16} />
          </Button>
        ) : null}
      </div>

      <div className="custom-scrollbar min-w-0 flex-1 space-y-4 overflow-x-hidden overflow-y-auto p-4">
        <section className="min-w-0 space-y-3 rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
          <div className="flex min-w-0 items-center gap-2 text-sm font-medium text-[var(--text-primary)]">
            <Brain size={16} className="shrink-0 text-indigo-500" />
            <span className="truncate">{t('spider.panel.model')}</span>
          </div>
          <button
            type="button"
            onClick={onOpenModelSettings}
            className="group w-full min-w-0 rounded-xl border border-[var(--border-color)] px-3 py-2.5 text-left transition-colors hover:border-indigo-500/30 hover:bg-[var(--bg-hover)]"
          >
            <div className="flex min-w-0 items-center justify-between gap-2">
              <span className="truncate font-mono text-sm text-[var(--text-primary)]">
                {selectedModel || t('spider.panel.modelUnset')}
              </span>
              <ChevronRight
                size={14}
                className="shrink-0 text-[var(--text-secondary)] transition-colors group-hover:text-indigo-500"
              />
            </div>
          </button>
        </section>

        <section className="min-w-0 space-y-3 rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
          <div className="flex min-w-0 items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-2 text-sm font-medium text-[var(--text-primary)]">
                <FolderOpen size={16} className="shrink-0 text-indigo-500" />
                <span className="truncate">{t('spider.panel.workspace')}</span>
              </div>
              <SpiderSessionScopeMeta
                sessionId={currentSessionId}
                title={sessionTitle}
                targetUrl={targetUrl}
                className="mt-1"
                indentClassName="pl-6"
              />
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <span className="tabular-nums text-[11px] text-[var(--text-secondary)]">
                {workspaceFiles.length}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => void refreshWorkspace()}
                disabled={!currentSessionId}
                aria-label={t('common.refresh', { defaultValue: '刷新' })}
              >
                <RefreshCw size={14} className={cn(isGenerating && 'animate-spin')} />
              </Button>
            </div>
          </div>

          {!currentSessionId ? (
            <div className="rounded-xl border border-dashed border-[var(--border-color)] p-5 text-center">
              <p className="break-words text-sm text-[var(--text-secondary)]">{t('spider.panel.noSession')}</p>
            </div>
          ) : workspaceFiles.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--border-color)] p-5 text-center">
              <p className="break-words text-sm text-[var(--text-secondary)]">
                {isGenerating ? t('spider.panel.syncing') : t('spider.panel.noFiles')}
              </p>
            </div>
          ) : (
            <ul className="min-w-0 space-y-2">
              {workspaceFiles.map((file) => (
                <li key={file.name} className="min-w-0">
                  <button
                    type="button"
                    onClick={() => {
                      if (!currentSessionId) return;
                      navigate(`/spider/files/${currentSessionId}?file=${encodeURIComponent(file.name)}`);
                    }}
                    className="flex w-full min-w-0 items-center gap-2.5 rounded-xl border border-[var(--border-color)] p-2.5 text-left transition-colors hover:border-indigo-500/20 hover:bg-[var(--bg-hover)]"
                  >
                    <div
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                      style={{ backgroundColor: spiderBranding.colors.primaryMuted }}
                    >
                      <FileCode2 size={14} className="text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-[var(--text-primary)]">{file.name}</p>
                      <p className="truncate text-[11px] text-[var(--text-secondary)]">
                        {formatFileSize(file.size)}
                        {file.modified_at ? ` · ${file.modified_at}` : ''}
                      </p>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="min-w-0 space-y-3 rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
          <div className="flex min-w-0 items-center gap-2 text-sm font-medium text-[var(--text-primary)]">
            <GitBranch size={16} className="shrink-0 text-indigo-500" />
            <span className="truncate">{t('spider.panel.flowTitle')}</span>
          </div>
          <ol className="min-w-0 space-y-2">
            {FLOW_STEP_KEYS.map((key, index) => (
              <li key={key} className="flex min-w-0 items-start gap-3">
                <span
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-indigo-600 dark:text-indigo-300"
                  style={{ backgroundColor: spiderBranding.colors.primaryMuted }}
                >
                  {index + 1}
                </span>
                <span className="min-w-0 flex-1 break-words pt-0.5 text-xs leading-relaxed text-[var(--text-secondary)]">
                  {t(`spider.panel.${key}`)}
                </span>
              </li>
            ))}
          </ol>
        </section>

        <div
          className={cn(
            'flex min-w-0 gap-2 rounded-xl border p-3 text-[11px] leading-relaxed',
            'border-amber-500/20 bg-amber-500/5 text-amber-900 dark:text-amber-100',
          )}
        >
          <AlertCircle size={14} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
          <p className="min-w-0 flex-1 break-words">{t('spider.panel.modelHint')}</p>
        </div>
      </div>
    </aside>
  );
}
