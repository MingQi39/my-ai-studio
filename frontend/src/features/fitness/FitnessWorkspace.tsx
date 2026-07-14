import React, { useEffect } from 'react';
import { Menu, PanelRight, UtensilsCrossed } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/button';
import { ActiveModelBadge } from '@/components/ActiveModelBadge';
import { EllipsisTooltip } from '@/components/EllipsisTooltip';
import { cn } from '@/components/ui/utils';

import { FitnessChatView } from '@/features/fitness/components/FitnessChatView';
import { fitnessBranding } from '@/features/fitness/config/branding';

interface FitnessWorkspaceProps {
  isDarkMode: boolean;
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  selectedModel: string;
  selectedModelConfigId: string | null;
  isControlPanelOpen: boolean;
  toggleControlPanel: () => void;
  onOpenModelSettings: () => void;
}

export function FitnessWorkspace({
  isDarkMode,
  isSidebarOpen,
  toggleSidebar,
  selectedModel,
  isControlPanelOpen,
  toggleControlPanel,
  onOpenModelSettings,
}: FitnessWorkspaceProps) {
  const { t } = useTranslation();

  useEffect(() => {
    if (isDarkMode) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  }, [isDarkMode]);

  return (
    <div className="flex flex-col h-full w-full bg-[var(--bg-main)] text-[var(--text-primary)]">
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
            style={{ backgroundColor: fitnessBranding.colors.primaryMuted }}
          >
            <UtensilsCrossed size={18} className="text-emerald-600 dark:text-emerald-400" />
          </div>

          <div className="min-w-0">
            <EllipsisTooltip as="h1" className="text-sm font-semibold">
              {t('fitness.sidebar.agentTitle')}
            </EllipsisTooltip>
            <EllipsisTooltip
              as="p"
              className="hidden text-xs text-[var(--text-secondary)] sm:block"
            >
              {t('fitness.sidebar.subtitle')}
            </EllipsisTooltip>
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
            className={cn('h-9 w-9', isControlPanelOpen && 'text-emerald-600 dark:text-emerald-400')}
            aria-label={t('fitness.panel.title')}
          >
            <PanelRight size={18} />
          </Button>
        </div>
      </header>

      <main className="flex-1 min-h-0 overflow-hidden">
        <FitnessChatView
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
