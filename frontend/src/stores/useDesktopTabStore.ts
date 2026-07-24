import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

export interface DesktopTab {
  id: string;
  path: string;
  pinned: boolean;
}

interface DesktopTabState {
  tabs: DesktopTab[];
  activeTabId: string | null;
  addTab: (path?: string) => DesktopTab;
  activateTab: (tabId: string) => void;
  closeTab: (tabId: string) => DesktopTab | null;
  syncPath: (path: string) => void;
  togglePin: (tabId: string) => void;
  reset: () => void;
}

function createTab(path = '/'): DesktopTab {
  const id =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `tab-${Date.now()}-${Math.random().toString(36).slice(2)}`;

  return { id, path, pinned: false };
}

function orderPinnedFirst(tabs: DesktopTab[]): DesktopTab[] {
  return [...tabs.filter((tab) => tab.pinned), ...tabs.filter((tab) => !tab.pinned)];
}

export const useDesktopTabStore = create<DesktopTabState>()(
  persist(
    (set, get) => ({
      tabs: [],
      activeTabId: null,

      addTab(path = '/') {
        const tab = createTab(path);
        set((state) => ({
          tabs: [...state.tabs, tab],
          activeTabId: tab.id,
        }));
        return tab;
      },

      activateTab(tabId) {
        set((state) =>
          state.tabs.some((tab) => tab.id === tabId)
            ? { activeTabId: tabId }
            : state,
        );
      },

      closeTab(tabId) {
        const state = get();
        const closingIndex = state.tabs.findIndex((tab) => tab.id === tabId);
        if (closingIndex === -1 || state.tabs[closingIndex].pinned) {
          return (
            state.tabs.find((tab) => tab.id === state.activeTabId) ??
            null
          );
        }

        const remainingTabs = state.tabs.filter((tab) => tab.id !== tabId);
        if (remainingTabs.length === 0) {
          const replacement = createTab('/');
          set({ tabs: [replacement], activeTabId: replacement.id });
          return replacement;
        }

        if (state.activeTabId !== tabId) {
          set({ tabs: remainingTabs });
          return (
            remainingTabs.find((tab) => tab.id === state.activeTabId) ??
            remainingTabs[0]
          );
        }

        const nextActiveTab =
          remainingTabs[Math.min(closingIndex, remainingTabs.length - 1)];
        set({ tabs: remainingTabs, activeTabId: nextActiveTab.id });
        return nextActiveTab;
      },

      syncPath(path) {
        set((state) => {
          if (state.tabs.length === 0 || !state.activeTabId) {
            const firstTab = createTab(path);
            return { tabs: [firstTab], activeTabId: firstTab.id };
          }

          const activeTab = state.tabs.find((tab) => tab.id === state.activeTabId);
          if (!activeTab) {
            const firstTab = state.tabs[0] ?? createTab(path);
            return {
              tabs: state.tabs.length > 0 ? state.tabs : [firstTab],
              activeTabId: firstTab.id,
            };
          }

          if (activeTab.path === path) return state;

          const matchingTab = state.tabs.find((tab) => tab.path === path);
          if (matchingTab) {
            return { activeTabId: matchingTab.id };
          }

          if (activeTab.pinned) {
            const tab = createTab(path);
            return {
              tabs: [...state.tabs, tab],
              activeTabId: tab.id,
            };
          }

          return {
            tabs: state.tabs.map((tab) =>
              tab.id === activeTab.id ? { ...tab, path } : tab,
            ),
          };
        });
      },

      togglePin(tabId) {
        set((state) => ({
          tabs: orderPinnedFirst(
            state.tabs.map((tab) =>
              tab.id === tabId ? { ...tab, pinned: !tab.pinned } : tab,
            ),
          ),
        }));
      },

      reset() {
        set({ tabs: [], activeTabId: null });
      },
    }),
    {
      name: 'qi-desktop-tabs',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        tabs: state.tabs,
        activeTabId: state.activeTabId,
      }),
    },
  ),
);
