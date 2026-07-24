import { useEffect, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Brain,
  Bug,
  Dumbbell,
  FileText,
  MapPin,
  MessageSquareText,
  Pin,
  PinOff,
  Plus,
  Settings2,
  TerminalSquare,
  X,
  type LucideIcon,
} from 'lucide-react';

import { cn } from '@/components/ui/utils';
import { useDesktopTabStore, type DesktopTab } from '@/stores/useDesktopTabStore';

interface TabPresentation {
  label: string;
  Icon: LucideIcon;
}

function useTabPresentation(path: string): TabPresentation {
  const { t } = useTranslation();
  const pathname = path.split(/[?#]/)[0];

  if (pathname.startsWith('/travel/')) {
    const section = pathname.split('/')[2];
    if (section === 'react') {
      return { label: t('travel.sidebar.react'), Icon: TerminalSquare };
    }
    if (section === 'tools') {
      return { label: t('travel.sidebar.tools'), Icon: TerminalSquare };
    }
    if (section === 'settings') {
      return { label: t('travel.sidebar.agentSettings'), Icon: Settings2 };
    }
    return { label: t('sidebar.travelAgent'), Icon: MapPin };
  }

  if (pathname.startsWith('/fitness')) {
    return { label: t('sidebar.fitnessAgent'), Icon: Dumbbell };
  }

  if (pathname.startsWith('/spider/files')) {
    return { label: t('spider.sidebar.files'), Icon: FileText };
  }

  if (pathname.startsWith('/spider')) {
    return { label: t('sidebar.spiderAgent'), Icon: Bug };
  }

  if (pathname.startsWith('/interview')) {
    return { label: t('desktopTabs.interview'), Icon: Brain };
  }

  return { label: t('desktopTabs.chat'), Icon: MessageSquareText };
}

function DesktopTabItem({
  tab,
  isActive,
  onActivate,
  onClose,
}: {
  tab: DesktopTab;
  isActive: boolean;
  onActivate: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const togglePin = useDesktopTabStore((state) => state.togglePin);
  const { label, Icon } = useTabPresentation(tab.path);

  return (
    <div
      className={cn(
        'group relative flex h-9 min-w-[132px] max-w-[210px] shrink-0 items-center rounded-t-xl border px-2.5 transition-colors duration-150',
        isActive
          ? 'z-10 border-[var(--border-color)] border-b-[var(--bg-main)] bg-[var(--bg-main)] text-[var(--text-primary)]'
          : 'border-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
      )}
      style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
      data-desktop-tab-active={isActive ? 'true' : undefined}
    >
      <button
        type="button"
        onClick={onActivate}
        className="flex min-w-0 flex-1 items-center gap-2 text-left"
        aria-label={tab.pinned ? `${label}, ${t('desktopTabs.pinned')}` : label}
        title={label}
      >
        <Icon size={15} strokeWidth={1.8} className="shrink-0" />
        <span className="truncate text-[13px] font-medium">{label}</span>
      </button>

      <div
        className={cn(
          'ml-1 flex shrink-0 items-center gap-0.5 transition-opacity',
          isActive || tab.pinned
            ? 'opacity-100'
            : 'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100',
        )}
      >
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            togglePin(tab.id);
          }}
          aria-label={tab.pinned ? t('desktopTabs.unpin') : t('desktopTabs.pin')}
          title={tab.pinned ? t('desktopTabs.unpin') : t('desktopTabs.pin')}
          className="flex h-6 w-6 items-center justify-center rounded-md hover:bg-[var(--bg-hover)]"
        >
          {tab.pinned ? <PinOff size={13} /> : <Pin size={13} />}
        </button>

        {!tab.pinned && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onClose();
            }}
            aria-label={t('desktopTabs.close')}
            title={t('desktopTabs.close')}
            className="flex h-6 w-6 items-center justify-center rounded-md hover:bg-[var(--bg-hover)]"
          >
            <X size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

export function DesktopTabBar() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const tabs = useDesktopTabStore((state) => state.tabs);
  const activeTabId = useDesktopTabStore((state) => state.activeTabId);
  const addTab = useDesktopTabStore((state) => state.addTab);
  const activateTab = useDesktopTabStore((state) => state.activateTab);
  const closeTab = useDesktopTabStore((state) => state.closeTab);
  const syncPath = useDesktopTabStore((state) => state.syncPath);
  const didRestoreRef = useRef(false);

  const currentPath = useMemo(
    () => `${location.pathname}${location.search}${location.hash}`,
    [location.hash, location.pathname, location.search],
  );

  useEffect(() => {
    const currentState = useDesktopTabStore.getState();

    if (!didRestoreRef.current) {
      didRestoreRef.current = true;
      const activeTab = currentState.tabs.find(
        (tab) => tab.id === currentState.activeTabId,
      );
      if (currentPath === '/' && activeTab?.path && activeTab.path !== '/') {
        navigate(activeTab.path, { replace: true });
        return;
      }
    }

    syncPath(currentPath);
  }, [currentPath, navigate, syncPath]);

  const handleAddTab = () => {
    addTab('/');
    navigate('/');
  };

  const handleActivateTab = (tab: DesktopTab) => {
    activateTab(tab.id);
    if (tab.path !== currentPath) {
      navigate(tab.path);
    }
  };

  const handleCloseTab = (tab: DesktopTab) => {
    const wasActive = tab.id === activeTabId;
    const nextActiveTab = closeTab(tab.id);
    if (wasActive && nextActiveTab && nextActiveTab.path !== currentPath) {
      navigate(nextActiveTab.path);
    }
  };

  return (
    <header
      className="flex h-11 shrink-0 items-end border-b border-[var(--border-color)] bg-[var(--bg-sidebar)] px-2"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
      aria-label={t('desktopTabs.tabBar')}
    >
      <div className="flex min-w-0 flex-1 items-end gap-0.5 overflow-x-auto px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {tabs.map((tab) => (
          <DesktopTabItem
            key={tab.id}
            tab={tab}
            isActive={tab.id === activeTabId}
            onActivate={() => handleActivateTab(tab)}
            onClose={() => handleCloseTab(tab)}
          />
        ))}
      </div>

      <button
        type="button"
        onClick={handleAddTab}
        aria-label={t('desktopTabs.newTab')}
        title={t('desktopTabs.newTab')}
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        className="mb-1 ml-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
      >
        <Plus size={17} />
      </button>
    </header>
  );
}
