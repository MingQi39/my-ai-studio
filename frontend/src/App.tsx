import React, { useState, useEffect, useCallback } from 'react';
import { Toaster, toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { AppSidebar } from './components/AppSidebar';
import { MainWorkspace } from './components/MainWorkspace';
import { ControlPanel } from './components/ControlPanel';
import { ConnectionModal } from './components/ConnectionModal';
import { AuthPage } from './components/AuthPage';
import {
  User,
  getToken,
  getStoredUser,
  logout,
  listModelConfigs,
  ModelConfigResponse,
  SystemInstructionResponse,
} from './services/api';

function configMatchesProvider(config: ModelConfigResponse, providerId: string): boolean {
  if (config.adapter_type === 'official' && config.provider === providerId) return true;
  return config.adapter_type === providerId;
}

export default function App() {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    document.title = t('common.appName');
  }, [t, i18n.language]);

  const [isConnectionModalOpen, setIsConnectionModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedModelConfigId, setSelectedModelConfigId] = useState<string | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState<string | undefined>(undefined);

  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isControlPanelOpen, setIsControlPanelOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('history');
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [enableReasoning, setEnableReasoning] = useState(true);

  const [modelConfigs, setModelConfigs] = useState<ModelConfigResponse[]>([]);
  const [hasModelConfig, setHasModelConfig] = useState<boolean | null>(null);

  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sessionRefreshTrigger, setSessionRefreshTrigger] = useState(0);

  const [currentInstruction, setCurrentInstruction] = useState<SystemInstructionResponse | null>(null);
  const [tempSystemPrompt, setTempSystemPrompt] = useState('');

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
        setSelectedModel(sortedConfigs[0].model_id);
        setSelectedModelConfigId(sortedConfigs[0].id);
      }
      return sortedConfigs;
    } catch (error) {
      console.error('Failed to load model configs:', error);
      setHasModelConfig(false);
      return [];
    }
  }, []);

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
    if (isAuthenticated) {
      loadModelConfigs();
    }
  }, [isAuthenticated, loadModelConfigs]);

  useEffect(() => {
    if (hasModelConfig === false && isAuthenticated) {
      const timer = setTimeout(() => setIsConnectionModalOpen(true), 500);
      return () => clearTimeout(timer);
    }
  }, [hasModelConfig, isAuthenticated]);

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
    setModelConfigs([]);
    setHasModelConfig(null);
  };

  const handleConfigSave = (modelName: string, configId: string) => {
    if (modelName) setSelectedModel(modelName);
    if (configId) setSelectedModelConfigId(configId);
    loadModelConfigs(false);
    setIsConnectionModalOpen(false);
  };

  const openConnectionModal = useCallback((providerId?: string) => {
    setSelectedProviderId(providerId);
    setIsConnectionModalOpen(true);
  }, []);

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
      setSelectedModel(config.model_id);
      setSelectedModelConfigId(config.id);
      toast.success(t('workspace.modelSwitched', { name: config.model_id }));
    },
    [modelConfigs, openConnectionModal, t],
  );

  const handleTabChange = (tab: string) => {
    if (tab === 'settings') {
      setIsConnectionModalOpen(true);
    } else if (tab === 'logout') {
      handleLogout();
    } else {
      setActiveTab(tab);
    }
  };

  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
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

  if (isCheckingAuth) {
    return (
      <div className="flex h-screen w-full items-center justify-center" style={{ backgroundColor: isDarkMode ? '#131314' : '#f5f5f5' }}>
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
    <div className="flex h-screen w-full overflow-hidden transition-colors duration-300" style={{ backgroundColor: 'var(--bg-main)' }}>
      <style>{globalStyles}</style>
      <style>{themeStyles}</style>
      <Toaster position="top-center" theme={isDarkMode ? 'dark' : 'light'} />

      <div
        className={`transition-all duration-300 ease-in-out overflow-hidden flex-shrink-0 border-r border-[var(--border-color)] ${isSidebarOpen ? 'w-[260px] opacity-100' : 'w-0 opacity-0'}`}
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

      <MainWorkspace
        isSidebarOpen={isSidebarOpen}
        toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        isDarkMode={isDarkMode}
        hasModelConfig={hasModelConfig}
        onOpenConnectionModal={openConnectionModal}
        onSelectProviderModel={handleSelectProviderModel}
        enableReasoning={enableReasoning}
        currentSessionId={currentSessionId}
        onSessionChange={setCurrentSessionId}
        sessionRefreshTrigger={sessionRefreshTrigger}
        onSessionsChange={refreshSessions}
        systemPrompt={currentInstruction?.content || tempSystemPrompt}
        modelConfigId={selectedModelConfigId}
        selectedModel={selectedModel}
        isControlPanelOpen={isControlPanelOpen}
        toggleControlPanel={() => setIsControlPanelOpen(!isControlPanelOpen)}
      />

      <div
        className={`transition-all duration-300 ease-in-out overflow-hidden flex-shrink-0 ${isControlPanelOpen ? 'w-[300px] opacity-100' : 'w-0 opacity-0'}`}
      >
        <ControlPanel
          onModelClick={() => setIsConnectionModalOpen(true)}
          selectedModel={selectedModel}
          isDarkMode={isDarkMode}
          enableReasoning={enableReasoning}
          onEnableReasoningChange={setEnableReasoning}
          currentInstruction={currentInstruction}
          onInstructionChange={setCurrentInstruction}
          tempSystemPrompt={tempSystemPrompt}
          onTempSystemPromptChange={setTempSystemPrompt}
          isOpen={isControlPanelOpen}
          togglePanel={() => setIsControlPanelOpen(!isControlPanelOpen)}
        />
      </div>

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
