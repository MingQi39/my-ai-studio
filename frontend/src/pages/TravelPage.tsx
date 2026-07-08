import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { TravelWorkspace } from '@/features/travel/TravelWorkspace';
import { TravelControlPanel } from '@/features/travel/TravelControlPanel';
import { TravelRuntimeContext } from '@/features/travel/TravelRuntimeContext';
import { useIsMobile } from '@/components/ui/use-mobile';
import { cn } from '@/components/ui/utils';

const VALID_TABS = ['chat', 'react', 'tools', 'settings'] as const;
type TravelTab = (typeof VALID_TABS)[number];

interface TravelPageProps {
  isDarkMode: boolean;
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  selectedModel: string;
  selectedModelConfigId: string | null;
  isControlPanelOpen: boolean;
  toggleControlPanel: () => void;
  onOpenModelSettings: () => void;
}

function TravelTabView({
  tab,
  ...props
}: Omit<TravelPageProps, 'selectedModelConfigId' | 'onOpenModelSettings'> & {
  tab: TravelTab;
  onOpenModelSettings: () => void;
}) {
  return (
    <div className="flex-1 min-w-0 h-full overflow-hidden flex flex-col">
      <TravelWorkspace activeTab={tab} {...props} />
    </div>
  );
}

export function TravelPage({
  isDarkMode,
  isSidebarOpen,
  toggleSidebar,
  selectedModel,
  selectedModelConfigId,
  isControlPanelOpen,
  toggleControlPanel,
  onOpenModelSettings,
}: TravelPageProps) {
  const isMobile = useIsMobile();
  const sharedProps = {
    isDarkMode,
    isSidebarOpen,
    toggleSidebar,
    selectedModel,
    isControlPanelOpen,
    toggleControlPanel,
    onOpenModelSettings,
  };

  return (
    <TravelRuntimeContext.Provider value={{ modelConfigId: selectedModelConfigId }}>
      <div className="flex flex-1 min-w-0 h-full overflow-hidden">
        <Routes>
          <Route index element={<Navigate to="chat" replace />} />
          <Route path="chat/:sessionId?" element={<TravelTabView tab="chat" {...sharedProps} />} />
          {VALID_TABS.filter((tab) => tab !== 'chat').map((tab) => (
            <Route key={tab} path={tab} element={<TravelTabView tab={tab} {...sharedProps} />} />
          ))}
          <Route path="*" element={<Navigate to="chat" replace />} />
        </Routes>

        {/* Control panel: desktop rail or mobile overlay */}
        {!isMobile ? (
          <div
            className={cn(
              'transition-all duration-300 ease-in-out overflow-hidden flex-shrink-0',
              isControlPanelOpen ? 'w-[300px] opacity-100' : 'w-0 opacity-0',
            )}
          >
            <TravelControlPanel
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
                'absolute inset-y-0 right-0 w-[min(300px,90vw)] shadow-2xl transition-transform duration-300 ease-in-out',
                isControlPanelOpen ? 'translate-x-0' : 'translate-x-full',
              )}
            >
              <TravelControlPanel
                selectedModel={selectedModel}
                onOpenModelSettings={onOpenModelSettings}
                isOpen={isControlPanelOpen}
                onClose={toggleControlPanel}
              />
            </div>
          </div>
        )}
      </div>
    </TravelRuntimeContext.Provider>
  );
}
