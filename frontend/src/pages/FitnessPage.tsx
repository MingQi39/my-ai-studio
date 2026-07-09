import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useIsMobile } from '@/components/ui/use-mobile';
import { cn } from '@/components/ui/utils';

import { FitnessWorkspace } from '@/features/fitness/FitnessWorkspace';
import { FitnessControlPanel } from '@/features/fitness/FitnessControlPanel';
import { FitnessRuntimeContext } from '@/features/fitness/FitnessRuntimeContext';

interface FitnessPageProps {
  isDarkMode: boolean;
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  selectedModel: string;
  selectedModelConfigId: string | null;
  isControlPanelOpen: boolean;
  toggleControlPanel: () => void;
  onOpenModelSettings: () => void;
}

export function FitnessPage({
  isDarkMode,
  isSidebarOpen,
  toggleSidebar,
  selectedModel,
  selectedModelConfigId,
  isControlPanelOpen,
  toggleControlPanel,
  onOpenModelSettings,
}: FitnessPageProps) {
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
    <FitnessRuntimeContext.Provider value={{ modelConfigId: selectedModelConfigId }}>
      <div className="flex flex-1 min-w-0 h-full overflow-hidden">
        <Routes>
          <Route index element={<Navigate to="chat" replace />} />
          <Route path="chat/:sessionId?" element={<FitnessWorkspace {...sharedProps} />} />
          <Route path="*" element={<Navigate to="chat" replace />} />
        </Routes>

        {/* Right control panel */}
        {!isMobile ? (
          <div
            className={cn(
              'transition-all duration-300 ease-in-out overflow-hidden flex-shrink-0',
              isControlPanelOpen ? 'w-[320px] opacity-100' : 'w-0 opacity-0',
            )}
          >
            <FitnessControlPanel
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
                'absolute inset-y-0 right-0 w-[min(320px,90vw)] shadow-2xl transition-transform duration-300 ease-in-out',
                isControlPanelOpen ? 'translate-x-0' : 'translate-x-full',
              )}
            >
              <FitnessControlPanel
                selectedModel={selectedModel}
                onOpenModelSettings={onOpenModelSettings}
                isOpen={isControlPanelOpen}
                onClose={toggleControlPanel}
              />
            </div>
          </div>
        )}
      </div>
    </FitnessRuntimeContext.Provider>
  );
}

