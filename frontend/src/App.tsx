import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Toaster, toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { AppSidebar } from './components/AppSidebar';
import { MainWorkspace } from './components/MainWorkspace';
import { ControlPanel, DEFAULT_CHAT_TOOLS_STATE, type ChatToolsState } from './components/ControlPanel';
import { ConnectionModal } from './components/ConnectionModal';
import { AuthPage } from './components/AuthPage';
import { TravelPage } from './pages/TravelPage';
import { FitnessPage } from './pages/FitnessPage';
import { SpiderPage } from './pages/SpiderPage';
import { InterviewPage } from './pages/InterviewPage';
import { branding } from './features/travel/config/branding';
import { fitnessBranding } from './features/fitness/config/branding';
import { spiderBranding } from './features/spider/config/branding';
import { useSessionRoute } from './hooks/useSessionRoute';
import { useIsMobile } from './components/ui/use-mobile';
import { cn } from './components/ui/utils';

import {
  User,
  getToken,
  getStoredUser,
  logout,
  listModelConfigs,
  ModelConfigResponse,
  SystemInstructionResponse,
  ApiError,
  getProviderIdFromConfig,
  getModelConfigDisplayName,
  pickActiveModelConfig,
  setStoredActiveModelConfigId,
  getSessionConfig,
  updateSessionConfig,
  type ChatToolsConfig,
} from './services/api';

function toToolsState(config: ChatToolsConfig | null | undefined): ChatToolsState {
  if (!config) return DEFAULT_CHAT_TOOLS_STATE;
  return {
    search: config.search,
    code: config.code,
    function: config.function,
    structured: config.structured,
  };
}

function configMatchesProvider(config: ModelConfigResponse, providerId: string): boolean {
  if (config.adapter_type === 'official' && config.provider === providerId) return true;
  return config.adapter_type === providerId;
}

function MainChatRoute({
  isSidebarOpen,
  toggleSidebar,
  isDarkMode,
  hasModelConfig,
  onOpenConnectionModal,
  onSelectProviderModel,
  enableReasoning,
  sessionRefreshTrigger,
  onSessionsChange,
  systemPrompt,
  modelConfigId,
  selectedModel,
  isControlPanelOpen,
  toggleControlPanel,
  toolsState,
  onToolsStateChange,
}: {
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  isDarkMode: boolean;
  hasModelConfig: boolean | null;
  onOpenConnectionModal: (selectedProviderId?: string) => void;
  onSelectProviderModel: (providerId: string, displayName: string) => void;
  enableReasoning: boolean;
  sessionRefreshTrigger: number;
  onSessionsChange: () => void;
  systemPrompt: string;
  modelConfigId: string | null;
  selectedModel: string;
  isControlPanelOpen: boolean;
  toggleControlPanel: () => void;
  toolsState: ChatToolsState;
  onToolsStateChange: (state: ChatToolsState) => void;
}) {
  const { currentSessionId, setCurrentSessionId } = useSessionRoute();

  return (
    <MainWorkspace
      isSidebarOpen={isSidebarOpen}
      toggleSidebar={toggleSidebar}
      isDarkMode={isDarkMode}
      hasModelConfig={hasModelConfig}
      onOpenConnectionModal={onOpenConnectionModal}
      onSelectProviderModel={onSelectProviderModel}
      enableReasoning={enableReasoning}
      currentSessionId={currentSessionId}
      onSessionChange={setCurrentSessionId}
      sessionRefreshTrigger={sessionRefreshTrigger}
      onSessionsChange={onSessionsChange}
      systemPrompt={systemPrompt}
      modelConfigId={modelConfigId}
      selectedModel={selectedModel}
      isControlPanelOpen={isControlPanelOpen}
      toggleControlPanel={toggleControlPanel}
      toolsState={toolsState}
      onToolsStateChange={onToolsStateChange}
    />
  );
}

export default function App() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const isMobile = useIsMobile();

  const isTravelRoute = location.pathname.startsWith('/travel');
  const isFitnessRoute = location.pathname.startsWith('/fitness');
  const isSpiderRoute = location.pathname.startsWith('/spider');
  const isInterviewRoute = location.pathname.startsWith('/interview');
  const activeTab = isSpiderRoute
    ? 'spider-agent'
    : isInterviewRoute
      ? 'interview-agent'
    : isFitnessRoute
      ? 'fitness-agent'
      : isTravelRoute
        ? 'travel-agent'
        : 'history';

  useEffect(() => {
    document.title = isTravelRoute
      ? branding.documentTitle
      : isFitnessRoute
        ? fitnessBranding.documentTitle
        : isSpiderRoute
          ? spiderBranding.documentTitle
          : t('common.appName');
  }, [t, i18n.language, isTravelRoute, isFitnessRoute, isSpiderRoute]);

  const [isConnectionModalOpen, setIsConnectionModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedModelConfigId, setSelectedModelConfigId] = useState<string | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState<string | undefined>(undefined);

  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  const [isSidebarOpen, setIsSidebarOpen] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth >= 768 : true,
  );
  const [isControlPanelOpen, setIsControlPanelOpen] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth >= 768 : true,
  );
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [enableReasoning, setEnableReasoning] = useState(true);
  const [toolsState, setToolsState] = useState<ChatToolsState>(DEFAULT_CHAT_TOOLS_STATE);

  const [modelConfigs, setModelConfigs] = useState<ModelConfigResponse[]>([]);
  const [hasModelConfig, setHasModelConfig] = useState<boolean | null>(null);

  const [currentInstruction, setCurrentInstruction] = useState<SystemInstructionResponse | null>(null);
  const [tempSystemPrompt, setTempSystemPrompt] = useState('');
  const [sessionRefreshTrigger, setSessionRefreshTrigger] = useState(0);

  const currentSessionId = location.pathname.match(/^\/session\/([^/]+)/)?.[1] ?? null;

  const applyActiveModelConfig = useCallback((config: ModelConfigResponse) => {
    setSelectedModel(getModelConfigDisplayName(config));
    setSelectedModelConfigId(config.id);
    setStoredActiveModelConfigId(config.id);
  }, []);

  const loadModelConfigs = useCallback(async (autoSelect: boolean = true) => {
    try {
      const configs = await listModelConfigs();
      const sortedConfigs = configs.sort((a, b) => {
        const dateA = new Date(a.updated_at).getTime();
        const dateB = new Date(b.updated_at).getTime();
        return dateB - dateA;
      });
      setModelConfigs(sortedConfigs);
      setHasModelConfig(sortedConfigs.length > 0);
      if (autoSelect && sortedConfigs.length > 0) {
        const activeConfig = pickActiveModelConfig(sortedConfigs);
        if (activeConfig) {
          applyActiveModelConfig(activeConfig);
        }
      }
      return sortedConfigs;
    } catch (error) {
      console.error('Failed to load model configs:', error);
      if (error instanceof ApiError && error.status === 401) {
        logout();
        setIsAuthenticated(false);
        setCurrentUser(null);
        setSelectedModel('');
        setSelectedModelConfigId(null);
        setStoredActiveModelConfigId(null);
        setModelConfigs([]);
        setHasModelConfig(null);
        toast.error(t('auth.sessionExpired'));
        return [];
      }
      setHasModelConfig(false);
      return [];
    }
  }, [applyActiveModelConfig, t]);

  useEffect(() => {
    const token = getToken();
    const storedUser = getStoredUser();
    if (token && storedUser) {
      setIsAuthenticated(true);
      setCurrentUser(storedUser);
    }
    setIsCheckingAuth(false);
  }, []);

  useEffect(() => {
    if (isMobile) {
      setIsSidebarOpen(false);
      setIsControlPanelOpen(false);
    }
  }, [isMobile]);

  useEffect(() => {
    if (isMobile) {
      setIsSidebarOpen(false);
    }
  }, [location.pathname, isMobile]);

  // When resizing from mobile → desktop, restore rails so the layout isn't stuck collapsed.
  const wasMobileRef = useRef(isMobile);
  useEffect(() => {
    if (wasMobileRef.current && !isMobile) {
      setIsSidebarOpen(true);
      setIsControlPanelOpen(true);
    }
    wasMobileRef.current = isMobile;
  }, [isMobile]);

  // Lock background scroll + Esc close while mobile drawers are open.
  useEffect(() => {
    if (!isMobile) return;
    const drawerOpen = isSidebarOpen || isControlPanelOpen;
    if (!drawerOpen) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsSidebarOpen(false);
        setIsControlPanelOpen(false);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [isMobile, isSidebarOpen, isControlPanelOpen]);

  useEffect(() => {
    if (isAuthenticated) {
      loadModelConfigs();
    }
  }, [isAuthenticated, loadModelConfigs]);

  useEffect(() => {
    if (!selectedModelConfigId || modelConfigs.length === 0) return;
    const activeConfig = modelConfigs.find((config) => config.id === selectedModelConfigId);
    if (activeConfig) {
      setSelectedModel(getModelConfigDisplayName(activeConfig));
    }
  }, [modelConfigs, selectedModelConfigId]);

  useEffect(() => {
    if (hasModelConfig === false && isAuthenticated) {
      const timer = setTimeout(() => setIsConnectionModalOpen(true), 500);
      return () => clearTimeout(timer);
    }
  }, [hasModelConfig, isAuthenticated]);

  useEffect(() => {
    if (!currentSessionId || !isAuthenticated) {
      setToolsState(DEFAULT_CHAT_TOOLS_STATE);
      return;
    }

    let cancelled = false;
    void getSessionConfig(currentSessionId)
      .then((config) => {
        if (!cancelled) {
          setToolsState(toToolsState(config.tools_config));
        }
      })
      .catch((error) => {
        console.error('Failed to load session tools config:', error);
        if (!cancelled) {
          setToolsState(DEFAULT_CHAT_TOOLS_STATE);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentSessionId, isAuthenticated]);

  const handleToolsStateChange = useCallback(
    (state: ChatToolsState) => {
      setToolsState(state);
      if (currentSessionId) {
        void updateSessionConfig(currentSessionId, { tools_config: state }).catch((error) => {
          console.error('Failed to save session tools config:', error);
        });
      }
    },
    [currentSessionId],
  );

  const handleAuthSuccess = (user: User) => {
    setCurrentUser(user);
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    logout();
    setIsAuthenticated(false);
    setCurrentUser(null);
    setSelectedModel('');
    setSelectedModelConfigId(null);
    setStoredActiveModelConfigId(null);
    setModelConfigs([]);
    setHasModelConfig(null);
  };

  const handleConfigSave = (modelName: string, configId: string) => {
    void loadModelConfigs(false).then((configs) => {
      const savedConfig = configs.find((config) => config.id === configId);
      if (savedConfig) {
        applyActiveModelConfig(savedConfig);
      } else if (configId) {
        setSelectedModel(modelName);
        setSelectedModelConfigId(configId);
        setStoredActiveModelConfigId(configId);
      }
    });
    setIsConnectionModalOpen(false);
  };

  const openConnectionModal = useCallback((providerId?: string) => {
    if (providerId) {
      setSelectedProviderId(providerId);
    } else if (selectedModelConfigId) {
      const activeConfig = modelConfigs.find((c) => c.id === selectedModelConfigId);
      setSelectedProviderId(activeConfig ? getProviderIdFromConfig(activeConfig) : undefined);
    } else {
      setSelectedProviderId(undefined);
    }
    setIsConnectionModalOpen(true);
  }, [selectedModelConfigId, modelConfigs]);

  const handleSelectProviderModel = useCallback(
    (providerId: string, displayName: string) => {
      const matches = modelConfigs
        .filter((c) => configMatchesProvider(c, providerId))
        .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
      const config = matches[0];
      if (!config) {
        toast.info(t('launchpad.configureFirst', { name: displayName }));
        openConnectionModal(providerId);
        return;
      }
      applyActiveModelConfig(config);
      toast.success(t('workspace.modelSwitched', { name: getModelConfigDisplayName(config) }));
    },
    [applyActiveModelConfig, modelConfigs, openConnectionModal, t],
  );

  const handleTabChange = (tab: string) => {
    if (tab === 'settings') {
      openConnectionModal();
    } else if (tab === 'logout') {
      handleLogout();
    } else if (tab === 'travel-agent') {
      navigate('/travel/chat');
      setIsControlPanelOpen(true);
    } else if (tab === 'fitness-agent') {
      navigate('/fitness/chat');
      setIsControlPanelOpen(true);
    } else if (tab === 'spider-agent') {
      navigate('/spider/chat');
      setIsControlPanelOpen(true);
    } else if (tab === 'interview-agent') {
      navigate('/interview');
      setIsControlPanelOpen(false);
    } else if (tab === 'history') {
      navigate('/');
      setIsControlPanelOpen(true);
    }
  };

  const handleSelectSession = (sessionId: string) => {
    navigate(`/session/${sessionId}`);
  };

  const refreshSessions = useCallback(() => {
    setSessionRefreshTrigger((prev) => prev + 1);
  }, []);

  const themeStyles = `
    :root {
      --bg-main: ${isDarkMode ? '#131314' : '#FFFFFF'};
      --bg-sidebar: ${isDarkMode ? '#1E1F20' : '#FFFFFF'};
      --bg-panel: ${isDarkMode ? '#1E1F20' : '#FFFFFF'};
      --bg-card: ${isDarkMode ? '#2D2E31' : '#FFFFFF'};
      --bg-input: ${isDarkMode ? '#1E1F20' : '#FFFFFF'};
      --bg-hover: ${isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)'};
      --nav-active-bg: ${isDarkMode ? '#36373A' : '#E8F0FE'};
      --nav-active-text: ${isDarkMode ? '#FFFFFF' : '#1967D2'};
      --text-primary: ${isDarkMode ? '#FFFFFF' : '#111827'};
      --text-secondary: ${isDarkMode ? '#8E9196' : '#6B7280'};
      --text-placeholder: ${isDarkMode ? '#5E6064' : '#9CA3AF'};
      --border-color: ${isDarkMode ? 'rgba(255,255,255,0.08)' : '#E5E7EB'};
      --border-hover: ${isDarkMode ? 'rgba(255,255,255,0.15)' : '#D1D5DB'};
      --accent-color: #3B82F6;
      --secondary: ${isDarkMode ? '#27272a' : '#f4f4f5'};
      --secondary-foreground: ${isDarkMode ? '#fafafa' : '#18181b'};
      --primary: ${isDarkMode ? '#3B82F6' : '#18181b'};
      --primary-foreground: ${isDarkMode ? '#18181b' : '#fafafa'};
      --ring: ${isDarkMode ? '#3B82F6' : '#18181b'};
      --input: ${isDarkMode ? '#27272a' : '#e4e4e7'};
    }
    .dark [data-orientation="horizontal"] > span:first-child {
      background-color: #3B82F6 !important;
    }
    .dark [data-orientation="horizontal"] {
      background-color: #333 !important;
    }
    .dark [data-state] > span {
      background-color: #000 !important;
      border: 1px solid #333;
    }
    body {
      background-color: var(--bg-main);
      color: var(--text-primary);
    }
    .custom-scrollbar::-webkit-scrollbar-thumb {
      background: ${isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.1)'};
    }
    .custom-scrollbar::-webkit-scrollbar-thumb:hover {
      background: ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.2)'};
    }
  `;

  const globalStyles = `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
    body {
      font-family: 'Inter', sans-serif;
      overflow: hidden;
      transition: background-color 0.3s ease, color 0.3s ease;
    }
    .custom-scrollbar::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    .custom-scrollbar::-webkit-scrollbar-track {
      background: transparent;
    }
    .custom-scrollbar::-webkit-scrollbar-thumb {
      border-radius: 3px;
    }
    pre, code {
      font-family: 'JetBrains Mono', monospace;
    }
    @keyframes shimmer {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(100%); }
    }
    .animate-shimmer {
      animation: shimmer 2s infinite linear;
    }
  `;

  const toggleSidebar = useCallback(() => {
    setIsSidebarOpen((open) => {
      const next = !open;
      if (next && isMobile) setIsControlPanelOpen(false);
      return next;
    });
  }, [isMobile]);

  const toggleControlPanel = useCallback(() => {
    setIsControlPanelOpen((open) => {
      const next = !open;
      if (next && isMobile) setIsSidebarOpen(false);
      return next;
    });
  }, [isMobile]);

  const showChatControlPanel = isControlPanelOpen && activeTab === 'history';

  if (isCheckingAuth) {
    return (
      <div className="flex h-dvh w-full items-center justify-center" style={{ backgroundColor: isDarkMode ? '#131314' : '#f5f5f5' }}>
        <style>{globalStyles}</style>
        <style>{themeStyles}</style>
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4" style={{ color: isDarkMode ? '#8E9196' : '#6B7280' }}>{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <>
        <style>{globalStyles}</style>
        <style>{themeStyles}</style>
        <AuthPage onAuthSuccess={handleAuthSuccess} isDarkMode={isDarkMode} toggleTheme={() => setIsDarkMode(!isDarkMode)} />
      </>
    );
  }

  return (
    <div className="flex h-dvh w-full overflow-hidden transition-colors duration-300" style={{ backgroundColor: 'var(--bg-main)' }}>
      <style>{globalStyles}</style>
      <style>{themeStyles}</style>
      <Toaster position="top-center" theme={isDarkMode ? 'dark' : 'light'} />

      {/* Sidebar: desktop rail or mobile overlay (single mount) */}
      {!isMobile ? (
        <div
          className={cn(
            'transition-all duration-300 ease-in-out overflow-hidden flex-shrink-0 border-r border-[var(--border-color)]',
            isSidebarOpen ? 'w-[260px] opacity-100' : 'w-0 opacity-0',
          )}
          style={{ backgroundColor: 'var(--bg-sidebar)' }}
        >
          <AppSidebar
            activeTab={activeTab}
            onTabChange={handleTabChange}
            isDarkMode={isDarkMode}
            toggleTheme={() => setIsDarkMode(!isDarkMode)}
            currentUser={currentUser}
            onLogout={handleLogout}
            currentSessionId={currentSessionId}
            onSelectSession={handleSelectSession}
            onSessionsChange={refreshSessions}
            sessionRefreshTrigger={sessionRefreshTrigger}
          />
        </div>
      ) : (
        <div
          className={cn(
            'fixed inset-0 z-40 transition-opacity duration-300',
            isSidebarOpen ? 'pointer-events-auto' : 'pointer-events-none',
          )}
          aria-hidden={!isSidebarOpen}
        >
          <button
            type="button"
            className={cn(
              'absolute inset-0 bg-black/50 transition-opacity duration-300',
              isSidebarOpen ? 'opacity-100' : 'opacity-0',
            )}
            onClick={() => setIsSidebarOpen(false)}
            aria-label="Close sidebar"
          />
          <div
            className={cn(
              'absolute inset-y-0 left-0 w-[min(280px,85vw)] border-r border-[var(--border-color)] shadow-2xl transition-transform duration-300 ease-in-out',
              isSidebarOpen ? 'translate-x-0' : '-translate-x-full',
            )}
            style={{ backgroundColor: 'var(--bg-sidebar)' }}
          >
            <AppSidebar
              activeTab={activeTab}
              onTabChange={handleTabChange}
              isDarkMode={isDarkMode}
              toggleTheme={() => setIsDarkMode(!isDarkMode)}
              currentUser={currentUser}
              onLogout={handleLogout}
              currentSessionId={currentSessionId}
              onSelectSession={handleSelectSession}
              onSessionsChange={refreshSessions}
              sessionRefreshTrigger={sessionRefreshTrigger}
            />
          </div>
        </div>
      )}

      <Routes>
        <Route
          path="/"
          element={
            <MainChatRoute
              isSidebarOpen={isSidebarOpen}
              toggleSidebar={toggleSidebar}
              isDarkMode={isDarkMode}
              hasModelConfig={hasModelConfig}
              onOpenConnectionModal={openConnectionModal}
              onSelectProviderModel={handleSelectProviderModel}
              enableReasoning={enableReasoning}
              sessionRefreshTrigger={sessionRefreshTrigger}
              onSessionsChange={refreshSessions}
              systemPrompt={currentInstruction?.content || tempSystemPrompt}
              modelConfigId={selectedModelConfigId}
              selectedModel={selectedModel}
              isControlPanelOpen={isControlPanelOpen}
              toggleControlPanel={toggleControlPanel}
              toolsState={toolsState}
              onToolsStateChange={handleToolsStateChange}
            />
          }
        />
        <Route
          path="/session/:sessionId"
          element={
            <MainChatRoute
              isSidebarOpen={isSidebarOpen}
              toggleSidebar={toggleSidebar}
              isDarkMode={isDarkMode}
              hasModelConfig={hasModelConfig}
              onOpenConnectionModal={openConnectionModal}
              onSelectProviderModel={handleSelectProviderModel}
              enableReasoning={enableReasoning}
              sessionRefreshTrigger={sessionRefreshTrigger}
              onSessionsChange={refreshSessions}
              systemPrompt={currentInstruction?.content || tempSystemPrompt}
              modelConfigId={selectedModelConfigId}
              selectedModel={selectedModel}
              isControlPanelOpen={isControlPanelOpen}
              toggleControlPanel={toggleControlPanel}
              toolsState={toolsState}
              onToolsStateChange={handleToolsStateChange}
            />
          }
        />
        <Route
          path="/travel/*"
          element={
            <TravelPage
              isDarkMode={isDarkMode}
              isSidebarOpen={isSidebarOpen}
              toggleSidebar={toggleSidebar}
              selectedModel={selectedModel}
              selectedModelConfigId={selectedModelConfigId}
              isControlPanelOpen={isControlPanelOpen}
              toggleControlPanel={toggleControlPanel}
              onOpenModelSettings={() => openConnectionModal()}
            />
          }
        />
        <Route
          path="/fitness/*"
          element={
            <FitnessPage
              isDarkMode={isDarkMode}
              isSidebarOpen={isSidebarOpen}
              toggleSidebar={toggleSidebar}
              selectedModel={selectedModel}
              selectedModelConfigId={selectedModelConfigId}
              isControlPanelOpen={isControlPanelOpen}
              toggleControlPanel={toggleControlPanel}
              onOpenModelSettings={() => openConnectionModal()}
            />
          }
        />
        <Route
          path="/spider/*"
          element={
            <SpiderPage
              isDarkMode={isDarkMode}
              isSidebarOpen={isSidebarOpen}
              toggleSidebar={toggleSidebar}
              selectedModel={selectedModel}
              selectedModelConfigId={selectedModelConfigId}
              isControlPanelOpen={isControlPanelOpen}
              toggleControlPanel={toggleControlPanel}
              onOpenModelSettings={() => openConnectionModal()}
            />
          }
        />
        <Route path="/interview" element={<InterviewPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* Control panel: desktop rail or mobile overlay */}
      {activeTab === 'history' &&
        (!isMobile ? (
          <div
            className={cn(
              'transition-all duration-300 ease-in-out overflow-hidden flex-shrink-0',
              showChatControlPanel ? 'w-[300px] opacity-100' : 'w-0 opacity-0',
            )}
          >
            <ControlPanel
              onModelClick={() => openConnectionModal()}
              selectedModel={selectedModel}
              isDarkMode={isDarkMode}
              enableReasoning={enableReasoning}
              onEnableReasoningChange={setEnableReasoning}
              currentInstruction={currentInstruction}
              onInstructionChange={setCurrentInstruction}
              tempSystemPrompt={tempSystemPrompt}
              onTempSystemPromptChange={setTempSystemPrompt}
              isOpen={isControlPanelOpen}
              togglePanel={toggleControlPanel}
              toolsState={toolsState}
              onToolsStateChange={handleToolsStateChange}
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
              onClick={() => setIsControlPanelOpen(false)}
              aria-label="Close settings panel"
            />
            <div
              className={cn(
                'absolute inset-y-0 right-0 w-[min(300px,90vw)] shadow-2xl transition-transform duration-300 ease-in-out',
                isControlPanelOpen ? 'translate-x-0' : 'translate-x-full',
              )}
            >
              <ControlPanel
                onModelClick={() => openConnectionModal()}
                selectedModel={selectedModel}
                isDarkMode={isDarkMode}
                enableReasoning={enableReasoning}
                onEnableReasoningChange={setEnableReasoning}
                currentInstruction={currentInstruction}
                onInstructionChange={setCurrentInstruction}
                tempSystemPrompt={tempSystemPrompt}
                onTempSystemPromptChange={setTempSystemPrompt}
                isOpen={isControlPanelOpen}
                togglePanel={toggleControlPanel}
                toolsState={toolsState}
                onToolsStateChange={handleToolsStateChange}
              />
            </div>
          </div>
        ))}

      <ConnectionModal
        isOpen={isConnectionModalOpen}
        onClose={() => {
          setIsConnectionModalOpen(false);
          setSelectedProviderId(undefined);
        }}
        isDarkMode={isDarkMode}
        onConfigSave={handleConfigSave}
        selectedProviderId={selectedProviderId}
      />
    </div>
  );
}
