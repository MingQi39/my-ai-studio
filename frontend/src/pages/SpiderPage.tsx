import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useIsMobile } from '@/components/ui/use-mobile';
import { cn } from '@/components/ui/utils';

import { SpiderWorkspace } from '@/features/spider/SpiderWorkspace';
import { SpiderFilesWorkspace } from '@/features/spider/SpiderFilesWorkspace';
import { SpiderControlPanel } from '@/features/spider/SpiderControlPanel';
import { SpiderRuntimeContext } from '@/features/spider/SpiderRuntimeContext';

interface SpiderPageProps {
  isDarkMode: boolean;
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  selectedModel: string;
  selectedModelConfigId: string | null;
  isControlPanelOpen: boolean;
  toggleControlPanel: () => void;
  onOpenModelSettings: () => void;
}

export function SpiderPage({
  isDarkMode,
  isSidebarOpen,
  toggleSidebar,
  selectedModel,
  selectedModelConfigId,
  isControlPanelOpen,
  toggleControlPanel,
  onOpenModelSettings,
}: SpiderPageProps) {
  const isMobile = useIsMobile();

  const sharedProps = {
    isDarkMode,
    isSidebarOpen,
    toggleSidebar,
    selectedModel,
    selectedModelConfigId,
    isControlPanelOpen,
    toggleControlPanel,
    onOpenModelSettings,
  };

  return (
    <SpiderRuntimeContext.Provider value={{ modelConfigId: selectedModelConfigId }}>
      <div className="flex flex-1 min-w-0 h-full overflow-hidden">
        {/* Must shrink beside the rail; otherwise w-full workspace + 320px panel overflows and clips the panel. */}
        <div className="flex-1 min-w-0 h-full overflow-hidden">
          <Routes>
            <Route index element={<Navigate to="chat" replace />} />
            <Route path="chat/:sessionId?" element={<SpiderWorkspace {...sharedProps} />} />
            <Route
              path="files/:sessionId?"
              element={
                <SpiderFilesWorkspace
                  isDarkMode={isDarkMode}
                  isSidebarOpen={isSidebarOpen}
                  toggleSidebar={toggleSidebar}
                  selectedModel={selectedModel}
                  onOpenModelSettings={onOpenModelSettings}
                />
              }
            />
            <Route path="*" element={<Navigate to="chat" replace />} />
          </Routes>
        </div>

        {!isMobile ? (
          <div
            className={cn(
              'transition-all duration-300 ease-in-out overflow-hidden flex-shrink-0',
              isControlPanelOpen ? 'w-[320px] opacity-100' : 'w-0 opacity-0',
            )}
          >
            <SpiderControlPanel
              selectedModel={selectedModel}
              onOpenModelSettings={onOpenModelSettings}
              isOpen={isControlPanelOpen}
              onClose={toggleControlPanel}
            />
          </div>
        ) : (
          <div
            className={cn(
              'fixed inset-0 z-40 transition-opacity duration-300',
              isControlPanelOpen ? 'pointer-events-auto' : 'pointer-events-none',
            )}
            aria-hidden={!isControlPanelOpen}
          >
            <button
              type="button"
              className={cn(
                'absolute inset-0 bg-black/50 transition-opacity duration-300',
                isControlPanelOpen ? 'opacity-100' : 'opacity-0',
              )}
              onClick={toggleControlPanel}
              aria-label="Close settings panel"
            />
            <div
              className={cn(
                'absolute inset-y-0 right-0 w-[min(320px,100vw)] max-w-full overflow-hidden shadow-2xl transition-transform duration-300 ease-in-out',
                isControlPanelOpen ? 'translate-x-0' : 'translate-x-full',
              )}
            >
              <SpiderControlPanel
                selectedModel={selectedModel}
                onOpenModelSettings={onOpenModelSettings}
                isOpen={isControlPanelOpen}
                onClose={toggleControlPanel}
              />
            </div>
          </div>
        )}
      </div>
    </SpiderRuntimeContext.Provider>
  );
}
