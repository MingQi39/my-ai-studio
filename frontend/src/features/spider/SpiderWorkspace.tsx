import React, { useEffect } from 'react';
import { Bug, Menu, PanelRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/button';
import { ActiveModelBadge } from '@/components/ActiveModelBadge';
import { cn } from '@/components/ui/utils';
import { SpiderChatView } from '@/features/spider/components/SpiderChatView';
import { spiderBranding } from '@/features/spider/config/branding';

interface SpiderWorkspaceProps {
  isDarkMode: boolean;
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  selectedModel: string;
  selectedModelConfigId: string | null;
  isControlPanelOpen: boolean;
  toggleControlPanel: () => void;
  onOpenModelSettings: () => void;
}

export function SpiderWorkspace({
  isDarkMode,
  isSidebarOpen,
  toggleSidebar,
  selectedModel,
  isControlPanelOpen,
  toggleControlPanel,
  onOpenModelSettings,
}: SpiderWorkspaceProps) {
  const { t } = useTranslation();

  useEffect(() => {
    if (isDarkMode) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  }, [isDarkMode]);

  return (
    <div className="flex h-full w-full min-w-0 flex-col bg-[var(--bg-main)] text-[var(--text-primary)]">
      <header className="h-14 flex-shrink-0 flex items-center justify-between px-3 sm:px-4 border-b border-[var(--border-color)] bg-[var(--bg-main)]/80 backdrop-blur-sm">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className={cn('h-9 w-9 shrink-0', isSidebarOpen ? 'md:hidden' : '')}
          >
            <Menu size={20} />
          </Button>

          <div
            className="w-9 h-9 rounded-xl hidden sm:flex items-center justify-center shrink-0"
            style={{ backgroundColor: spiderBranding.colors.primaryMuted }}
          >
            <Bug size={18} className="text-indigo-600 dark:text-indigo-400" />
          </div>

          <div className="min-w-0">
            <h1 className="text-sm font-semibold truncate">{t('spider.sidebar.agentTitle')}</h1>
            <p className="text-xs text-[var(--text-secondary)] truncate hidden sm:block">
              {t('spider.sidebar.subtitle')}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
          <ActiveModelBadge
            model={selectedModel}
            onClick={onOpenModelSettings}
            className="hidden sm:inline-flex"
          />
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleControlPanel}
            className={cn('h-9 w-9', isControlPanelOpen && 'text-indigo-600 dark:text-indigo-400')}
            aria-label={t('spider.panel.title')}
          >
            <PanelRight size={18} />
          </Button>
        </div>
      </header>

      <main className="flex-1 min-h-0 overflow-hidden">
        <SpiderChatView
          isDarkMode={isDarkMode}
          selectedModel={selectedModel}
          onOpenModelSettings={onOpenModelSettings}
          isControlPanelOpen={isControlPanelOpen}
          onOpenPanel={toggleControlPanel}
        />
      </main>
    </div>
  );
}
