import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { MessageSquare, Settings, Moon, Sun, Sparkles, ChevronRight, LogOut, ChevronDown, Trash2, MapPin, ArrowLeft, Brain, Wrench, Plus, UtensilsCrossed } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Separator } from '@/components/ui/separator';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { User, SessionResponse, listSessions, deleteSession as apiDeleteSession } from '@/services/api';
import { BrandLogo } from '@/components/BrandLogo';
import { useChatStore } from '@/features/travel/stores/useChatStore';
import { useFitnessChatStore } from '@/features/fitness/stores/useFitnessChatStore';
import {
  listTravelSessions,
  removeTravelSession,
} from '@/features/travel/services/api/sessions';
import { listFitnessSessions, removeFitnessSession } from '@/features/fitness/services/api/sessions';

interface AppSidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  isDarkMode: boolean;
  toggleTheme: () => void;
  currentUser?: User | null;
  onLogout?: () => void;
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onSessionsChange?: () => void;
  sessionRefreshTrigger?: number;
}

export function AppSidebar({
  activeTab,
  onTabChange,
  isDarkMode,
  toggleTheme,
  currentUser,
  onLogout,
  currentSessionId,
  onSelectSession,
  onSessionsChange,
  sessionRefreshTrigger
}: AppSidebarProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const travelSubTab = location.pathname.startsWith('/travel/')
    ? location.pathname.replace(/^\/travel\/?/, '').split('/')[0] || 'chat'
    : 'chat';
  const fitnessSubTab = location.pathname.startsWith('/fitness/')
    ? location.pathname.replace(/^\/fitness\/?/, '').split('/')[0] || 'chat'
    : 'chat';
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);
  const [isTravelHistoryOpen, setIsTravelHistoryOpen] = useState(true);
  const [isFitnessHistoryOpen, setIsFitnessHistoryOpen] = useState(true);
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [travelSessions, setTravelSessions] = useState<SessionResponse[]>([]);
  const [fitnessSessions, setFitnessSessions] = useState<SessionResponse[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isLoadingTravelSessions, setIsLoadingTravelSessions] = useState(false);
  const [isLoadingFitnessSessions, setIsLoadingFitnessSessions] = useState(false);
  const travelSessionId = useChatStore((state) => state.currentSessionId);
  const travelSessionListVersion = useChatStore((state) => state.sessionListVersion);
  const fitnessSessionId = useFitnessChatStore((state) => state.currentSessionId);
  const fitnessSessionListVersion = useFitnessChatStore((state) => state.sessionListVersion);

  // 确认对话框状态
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);
  const [sessionToDeleteIsTravel, setSessionToDeleteIsTravel] = useState(false);
  const [sessionToDeleteIsFitness, setSessionToDeleteIsFitness] = useState(false);

  // 加载会话列表
  const loadSessions = async () => {
    try {
      setIsLoadingSessions(true);
      const response = await listSessions(1, 50, false, 'chat');
      setSessions(response.items);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    } finally {
      setIsLoadingSessions(false);
    }
  };

  const loadTravelSessions = async () => {
    try {
      setIsLoadingTravelSessions(true);
      const items = await listTravelSessions();
      setTravelSessions(items);
    } catch (error) {
      console.error('Failed to load travel sessions:', error);
    } finally {
      setIsLoadingTravelSessions(false);
    }
  };

  const loadFitnessSessions = async () => {
    try {
      setIsLoadingFitnessSessions(true);
      const items = await listFitnessSessions();
      setFitnessSessions(items);
    } catch (error) {
      console.error('Failed to load fitness sessions:', error);
    } finally {
      setIsLoadingFitnessSessions(false);
    }
  };

  // 当展开历史会话或触发器变化时加载
  useEffect(() => {
    if (isHistoryOpen && activeTab !== 'travel-agent' && activeTab !== 'fitness-agent') {
      loadSessions();
    }
  }, [isHistoryOpen, sessionRefreshTrigger, activeTab]);

  useEffect(() => {
    if (activeTab === 'travel-agent' && isTravelHistoryOpen) {
      loadTravelSessions();
    }
  }, [activeTab, isTravelHistoryOpen, sessionRefreshTrigger, travelSessionListVersion]);

  useEffect(() => {
    if (activeTab === 'fitness-agent' && isFitnessHistoryOpen) {
      loadFitnessSessions();
    }
  }, [activeTab, isFitnessHistoryOpen, sessionRefreshTrigger, fitnessSessionListVersion]);

  const handleLogout = () => {
    if (onLogout) {
      onLogout();
      toast.success(t('sidebar.loggedOut'));
    }
  };

  const handleDeleteSession = async (
    sessionId: string,
    e: React.MouseEvent,
    isTravel = false,
    isFitness = false,
  ) => {
    e.stopPropagation();
    setSessionToDelete(sessionId);
    setSessionToDeleteIsTravel(isTravel);
    setSessionToDeleteIsFitness(isFitness);
    setIsDeleteDialogOpen(true);
  };

  const handleSelectTravelSession = (sessionId: string) => {
    navigate(`/travel/chat/${sessionId}`);
  };

  const handleNewTravelSession = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    useChatStore.getState().startNewSession();
    navigate('/travel/chat');
  };

  const handleSelectFitnessSession = (sessionId: string) => {
    navigate(`/fitness/chat/${sessionId}`);
  };

  const handleNewFitnessSession = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    useFitnessChatStore.getState().startNewSession();
    navigate('/fitness/chat');
  };

  const confirmDeleteSession = async () => {
    if (!sessionToDelete) return;

    try {
      if (sessionToDeleteIsTravel) {
        await removeTravelSession(sessionToDelete);
        setTravelSessions(prev => prev.filter(s => s.id !== sessionToDelete));
        if (travelSessionId === sessionToDelete) {
          useChatStore.getState().startNewSession();
          navigate('/travel/chat');
        }
      } else if (sessionToDeleteIsFitness) {
        await removeFitnessSession(sessionToDelete);
        setFitnessSessions(prev => prev.filter(s => s.id !== sessionToDelete));
        useFitnessChatStore.getState().bumpSessionList();
        if (fitnessSessionId === sessionToDelete) {
          useFitnessChatStore.getState().startNewSession();
          navigate('/fitness/chat');
        }
      } else {
        await apiDeleteSession(sessionToDelete);
        setSessions(prev => prev.filter(s => s.id !== sessionToDelete));

        if (currentSessionId === sessionToDelete) {
          navigate('/');
        }
      }

      toast.success(t('sidebar.sessionDeleted'), { id: 'session-deleted' });
      onSessionsChange?.();
    } catch (error) {
      console.error('Failed to delete session:', error);
      toast.error(t('sidebar.deleteFailed'));
    } finally {
      setSessionToDelete(null);
      setSessionToDeleteIsTravel(false);
      setSessionToDeleteIsFitness(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) return t('common.today');
    if (days === 1) return t('common.yesterday');
    if (days < 7) return t('common.daysAgo', { count: days });
    return date.toLocaleDateString(i18n.language, { month: 'short', day: 'numeric' });
  };

  return (
    <div className="w-full h-full flex flex-col min-w-0">

      {/* Header */}
      <button
        type="button"
        onClick={() => navigate('/')}
        className="h-[70px] w-full flex items-center px-5 gap-3 pt-2 flex-shrink-0 cursor-pointer hover:opacity-80 transition-opacity text-left group"
      >
        <BrandLogo size="sm" className="group-hover:shadow-md transition-shadow" alt={t('common.appName')} />
        <h1 className="font-semibold text-[18px] tracking-tight text-[var(--text-primary)]">{t('common.appName')}</h1>
      </button>

      {/* Navigation - Scrollable */}
      <ScrollArea className="flex-1 px-3 mt-4 min-w-0 w-full custom-scrollbar">
        <div className="flex flex-col gap-1 pb-4 min-w-0 w-full max-w-full">
          {activeTab === 'travel-agent' ? (
            <>
              <button
                onClick={() => navigate('/')}
                className="flex items-center gap-2 px-3 h-[36px] rounded-lg text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors mb-2"
              >
                <ArrowLeft size={16} />
                {t('travel.sidebar.backToWorkspace')}
              </button>

              <p className="px-3 pt-1 pb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                {t('sidebar.travelAgent')}
              </p>

              <NavButton
                icon={<Plus size={20} />}
                label={t('travel.sidebar.newChat')}
                id="travel-new-chat"
                isActive={travelSubTab === 'chat' && !travelSessionId}
                onClick={() => handleNewTravelSession()}
              />

              <Collapsible open={isTravelHistoryOpen} onOpenChange={setIsTravelHistoryOpen} className="mt-1">
                <div className="flex items-center justify-between px-3 mb-1">
                  <CollapsibleTrigger asChild>
                    <button
                      type="button"
                      onClick={() => {
                        const id = useChatStore.getState().currentSessionId;
                        navigate(id ? `/travel/chat/${id}` : '/travel/chat');
                      }}
                      className={`flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider transition-colors ${
                        travelSubTab === 'chat' && travelSessionId
                          ? 'text-blue-500'
                          : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                      }`}
                    >
                      <ChevronDown
                        size={12}
                        className={`transition-transform duration-200 ${isTravelHistoryOpen ? 'rotate-180' : ''}`}
                      />
                      {t('travel.sidebar.history')}
                    </button>
                  </CollapsibleTrigger>
                  <button
                    type="button"
                    onClick={handleNewTravelSession}
                    className="p-1 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    title={t('travel.sidebar.newChat')}
                  >
                    <Plus size={14} />
                  </button>
                </div>

                <CollapsibleContent>
                  <div className="pl-2 space-y-0.5 min-w-0">
                    {isLoadingTravelSessions ? (
                      <div className="py-4 text-center text-xs text-[var(--text-secondary)]">
                        {t('common.loading')}
                      </div>
                    ) : travelSessions.length === 0 ? (
                      <div className="py-4 text-center text-xs text-[var(--text-secondary)]">
                        {t('travel.sidebar.noSessions')}
                      </div>
                    ) : (
                      travelSessions
                        .slice(0, 20)
                        .map((session) => (
                          <AgentSessionHistoryRow
                            key={session.id}
                            session={session}
                            isActive={travelSessionId === session.id}
                            formatDate={formatDate}
                            onSelect={() => handleSelectTravelSession(session.id)}
                            onDelete={(e) => handleDeleteSession(session.id, e, true)}
                          />
                        ))
                    )}
                  </div>
                </CollapsibleContent>
              </Collapsible>

              <NavButton
                icon={<Brain size={20} />}
                label={t('travel.sidebar.react')}
                id="travel-react"
                isActive={travelSubTab === 'react'}
                onClick={() => navigate('/travel/react')}
              />
              <NavButton
                icon={<Wrench size={20} />}
                label={t('travel.sidebar.tools')}
                id="travel-tools"
                isActive={travelSubTab === 'tools'}
                onClick={() => navigate('/travel/tools')}
              />
              <NavButton
                icon={<Settings size={20} />}
                label={t('travel.sidebar.agentSettings')}
                id="travel-settings"
                isActive={travelSubTab === 'settings'}
                onClick={() => navigate('/travel/settings')}
              />

            </>
          ) : activeTab === 'fitness-agent' ? (
            <>
              <button
                onClick={() => navigate('/')}
                className="flex items-center gap-2 px-3 h-[36px] rounded-lg text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors mb-2"
              >
                <ArrowLeft size={16} />
                {t('fitness.sidebar.backToWorkspace')}
              </button>

              <p className="px-3 pt-1 pb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                {t('sidebar.fitnessAgent')}
              </p>

              <NavButton
                icon={<Plus size={20} />}
                label={t('fitness.sidebar.newChat')}
                id="fitness-new-chat"
                isActive={fitnessSubTab === 'chat' && !fitnessSessionId}
                onClick={() => handleNewFitnessSession()}
              />

              <Collapsible open={isFitnessHistoryOpen} onOpenChange={setIsFitnessHistoryOpen} className="mt-1">
                <div className="flex items-center justify-between px-3 mb-1">
                  <CollapsibleTrigger asChild>
                    <button
                      type="button"
                      onClick={() => {
                        const id = useFitnessChatStore.getState().currentSessionId;
                        navigate(id ? `/fitness/chat/${id}` : '/fitness/chat');
                      }}
                      className={`flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider transition-colors ${
                        fitnessSubTab === 'chat' && fitnessSessionId
                          ? 'text-blue-500'
                          : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                      }`}
                    >
                      <ChevronDown
                        size={12}
                        className={`transition-transform duration-200 ${isFitnessHistoryOpen ? 'rotate-180' : ''}`}
                      />
                      {t('fitness.sidebar.history')}
                    </button>
                  </CollapsibleTrigger>
                  <button
                    type="button"
                    onClick={handleNewFitnessSession}
                    className="p-1 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    title={t('fitness.sidebar.newChat')}
                  >
                    <Plus size={14} />
                  </button>
                </div>

                <CollapsibleContent>
                  <div className="pl-2 space-y-0.5 min-w-0">
                    {isLoadingFitnessSessions ? (
                      <div className="py-4 text-center text-xs text-[var(--text-secondary)]">{t('common.loading')}</div>
                    ) : fitnessSessions.length === 0 ? (
                      <div className="py-4 text-center text-xs text-[var(--text-secondary)]">{t('fitness.sidebar.noSessions')}</div>
                    ) : (
                      fitnessSessions
                        .slice(0, 20)
                        .map((session) => (
                          <AgentSessionHistoryRow
                            key={session.id}
                            session={session}
                            isActive={fitnessSessionId === session.id}
                            formatDate={formatDate}
                            onSelect={() => handleSelectFitnessSession(session.id)}
                            onDelete={(e) => handleDeleteSession(session.id, e, false, true)}
                          />
                        ))
                    )}
                  </div>
                </CollapsibleContent>
              </Collapsible>
            </>
          ) : (
            <>
              {/* 历史会话 - 可折叠 */}
              <Collapsible open={isHistoryOpen} onOpenChange={setIsHistoryOpen}>
                <CollapsibleTrigger asChild>
                  <button
                    onClick={() => onTabChange('history')}
                    className={`
                  w-full flex items-center justify-between px-3 h-[40px] rounded-lg text-sm font-medium transition-all group
                  ${activeTab === 'history' && isHistoryOpen
                    ? 'bg-[var(--nav-active-bg)] text-[var(--nav-active-text)]'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'}
                `}
                  >
                    <div className="flex items-center gap-3">
                      <MessageSquare size={20} />
                      <span>{t('sidebar.history')}</span>
                    </div>
                    <ChevronDown
                      size={14}
                      className={`transition-transform duration-200 ${isHistoryOpen ? 'rotate-180' : ''}`}
                    />
                  </button>
                </CollapsibleTrigger>

                <CollapsibleContent className="mt-1">
                  <div className="pl-2 space-y-0.5 min-w-0">
                    {isLoadingSessions ? (
                      <div className="py-4 text-center text-xs text-[var(--text-secondary)]">
                        {t('common.loading')}
                      </div>
                    ) : sessions.length === 0 ? (
                      <div className="py-4 text-center text-xs text-[var(--text-secondary)]">
                        {t('sidebar.noSessions')}
                      </div>
                    ) : (
                      sessions
                        .filter(session => session.message_count > 0)
                        .slice(0, 10)
                        .map((session) => (
                          <AgentSessionHistoryRow
                            key={session.id}
                            session={session}
                            isActive={currentSessionId === session.id}
                            formatDate={formatDate}
                            onSelect={() => navigate(`/session/${session.id}`)}
                            onDelete={(e) => handleDeleteSession(session.id, e)}
                          />
                        ))
                    )}
                  </div>
                </CollapsibleContent>
              </Collapsible>

              <NavButton
                icon={<MapPin size={20} />}
                label={t('sidebar.travelAgent')}
                id="travel-agent"
                isActive={activeTab === 'travel-agent'}
                onClick={() => onTabChange('travel-agent')}
                hasBadge
              />
              <NavButton
                icon={<UtensilsCrossed size={20} />}
                label={t('sidebar.fitnessAgent')}
                id="fitness-agent"
                isActive={activeTab === 'fitness-agent'}
                onClick={() => onTabChange('fitness-agent')}
                hasBadge
              />
            </>
          )}
        </div>
      </ScrollArea>

      {/* Bottom Section (Footer) */}
      <div className="px-3 pb-6 flex-shrink-0">
        <div className="flex flex-col gap-1">
          <Separator className="bg-[var(--border-color)] my-3 opacity-50" />

          {/* Theme Toggle */}
          <button
            onClick={() => {
              toggleTheme();
              toast.success(t('sidebar.themeSwitched', { mode: isDarkMode ? t('sidebar.lightMode') : t('sidebar.darkMode') }));
            }}
            className="flex items-center gap-3 px-3 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors group w-full"
          >
            {isDarkMode ? (
              <Sun size={20} className="group-hover:text-[var(--text-primary)] transition-colors" />
            ) : (
              <Moon size={20} className="group-hover:text-[var(--text-primary)] transition-colors" />
            )}
            <span className="text-sm font-medium group-hover:text-[var(--text-primary)] transition-colors">
              {isDarkMode ? t('sidebar.lightMode') : t('sidebar.darkMode')}
            </span>
          </button>

          {/* Language Switcher */}
          <LanguageSwitcher dropUp />

          {/* Settings */}
          <NavButton
            icon={<Settings size={20} />}
            label={t('sidebar.settings')}
            id="settings"
            isActive={activeTab === 'settings'}
            onClick={() => onTabChange('settings')}
          />

          {/* User Profile Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-[var(--bg-hover)] transition-colors w-full group mt-1 select-none text-left"
              >
                <Avatar className="h-6 w-6 border border-[var(--border-color)]">
                  <AvatarImage src="https://github.com/MingQi39.png" />
                  <AvatarFallback>{currentUser?.username?.charAt(0).toUpperCase() || 'U'}</AvatarFallback>
                </Avatar>
                <span className="text-sm font-medium text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors truncate flex-1">
                  {currentUser?.username || t('sidebar.user')}
                </span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              side="top"
              align="start"
              className="w-56 border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-primary)]"
            >
              {currentUser && (
                <>
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-sm font-medium truncate">{currentUser.username}</span>
                      <span className="text-xs text-[var(--text-secondary)] truncate">{currentUser.email}</span>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator className="bg-[var(--border-color)]" />
                </>
              )}
              <DropdownMenuItem
                variant="destructive"
                onClick={handleLogout}
                className="cursor-pointer"
              >
                <LogOut size={16} />
                {t('sidebar.logout')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* 确认删除对话框 */}
      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onClose={() => {
          setIsDeleteDialogOpen(false);
          setSessionToDelete(null);
          setSessionToDeleteIsTravel(false);
          setSessionToDeleteIsFitness(false);
        }}
        onConfirm={confirmDeleteSession}
        title={t('sidebar.deleteSessionTitle')}
        message={t('sidebar.deleteSessionMessage')}
        confirmText={t('common.delete')}
        cancelText={t('common.cancel')}
        isDarkMode={isDarkMode}
        type="danger"
      />
    </div>
  );
}

interface NavButtonProps {
  icon: React.ReactNode;
  label: string;
  id: string;
  isActive?: boolean;
  hasBadge?: boolean;
  accent?: 'default' | 'emerald';
  onClick?: () => void;
}

function NavButton({
  icon,
  label,
  isActive = false,
  hasBadge = false,
  accent = 'default',
  onClick,
}: NavButtonProps) {
  const activeClasses =
    accent === 'emerald'
      ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
      : 'bg-[var(--nav-active-bg)] text-[var(--nav-active-text)]';

  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-3 px-3 h-[40px] rounded-lg text-sm font-medium transition-all w-full text-left group
        ${isActive ? activeClasses : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'}
      `}
    >
      <span className={isActive ? '' : 'group-hover:text-[var(--text-primary)]'}>{icon}</span>
      <span className="flex-1">{label}</span>
      {hasBadge && (
        <Sparkles size={14} className="text-blue-400 fill-blue-400/20" />
      )}
      <ChevronRight size={14} className={`transition-opacity ${isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} />
    </button>
  );
}

interface AgentSessionHistoryRowProps {
  session: SessionResponse;
  isActive: boolean;
  formatDate: (dateString: string) => string;
  onSelect: () => void;
  onDelete: (e: React.MouseEvent) => void;
}

function AgentSessionHistoryRow({
  session,
  isActive,
  formatDate,
  onSelect,
  onDelete,
}: AgentSessionHistoryRowProps) {
  const { t } = useTranslation();

  return (
    <div
      onClick={onSelect}
      className={`
        relative group grid w-full max-w-full grid-cols-[1rem_minmax(0,1fr)_2rem] items-center gap-x-2 px-2 py-2 rounded-md cursor-pointer
        transition-all duration-200 text-xs
        ${isActive
          ? 'bg-blue-500/10 text-blue-500'
          : 'hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]'}
      `}
    >
      {isActive && (
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 bg-blue-500 rounded-r-full" />
      )}

      <MessageSquare size={14} className="shrink-0" />

      <div className="min-w-0 overflow-hidden">
        <p className="truncate font-medium">
          {session.title || t('sidebar.untitledSession')}
        </p>
        <p className="text-[10px] text-[var(--text-secondary)] truncate">
          {t('sidebar.messageCount', { count: session.message_count })} · {formatDate(session.updated_at)}
        </p>
      </div>

      <button
        type="button"
        onClick={onDelete}
        className="flex h-7 w-7 shrink-0 items-center justify-center justify-self-end rounded text-[var(--text-secondary)] opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto hover:bg-red-500/10 hover:text-red-500 transition-all"
        aria-label={t('sidebar.deleteSessionTitle')}
      >
        <Trash2 size={12} className="shrink-0" />
      </button>
    </div>
  );
}
