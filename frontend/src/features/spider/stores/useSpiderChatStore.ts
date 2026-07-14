import { create } from 'zustand';

import type { StudioChatMessage } from '@/hooks/studioChat/types';
import type { SpiderWorkspaceFile } from '@/features/spider/services/api/spider';
import {
  SPIDER_ACTIVE_SESSION_KEY,
  SPIDER_DRAFT_TARGET_URL_KEY,
  SPIDER_GENERATING_SESSION_KEY,
  spiderTargetUrlStorageKey,
} from '@/features/spider/constants/session';

function syncActiveSessionId(sessionId: string | null) {
  if (sessionId) {
    sessionStorage.setItem(SPIDER_ACTIVE_SESSION_KEY, sessionId);
  } else {
    sessionStorage.removeItem(SPIDER_ACTIVE_SESSION_KEY);
  }
}

interface SpiderChatStore {
  messages: StudioChatMessage[];
  currentSessionId: string | null;
  isGenerating: boolean;
  isLoadingHistory: boolean;
  sessionListVersion: number;
  sessionEpoch: number;
  targetUrl: string;
  workspaceFiles: SpiderWorkspaceFile[];
  restoreInterruptedHint: boolean;

  addMessage: (message: StudioChatMessage) => void;
  updateMessage: (id: string, updates: Partial<StudioChatMessage>) => void;
  setMessages: (messages: StudioChatMessage[]) => void;
  setCurrentSessionId: (sessionId: string | null) => void;
  setGenerating: (generating: boolean) => void;
  setLoadingHistory: (loading: boolean) => void;
  bumpSessionList: () => void;
  clearMessages: () => void;
  startNewSession: () => void;
  setTargetUrl: (url: string) => void;
  setWorkspaceFiles: (files: SpiderWorkspaceFile[]) => void;
  setRestoreInterruptedHint: (value: boolean) => void;
}

export const useSpiderChatStore = create<SpiderChatStore>((set) => ({
  messages: [],
  currentSessionId: null,
  isGenerating: false,
  isLoadingHistory: false,
  sessionListVersion: 0,
  sessionEpoch: 0,
  targetUrl: '',
  workspaceFiles: [],
  restoreInterruptedHint: false,

  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),

  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((msg) => (msg.id === id ? { ...msg, ...updates } : msg)),
    })),

  setMessages: (messages) => set({ messages }),
  setCurrentSessionId: (sessionId) => {
    syncActiveSessionId(sessionId);
    if (sessionId && useSpiderChatStore.getState().isGenerating) {
      sessionStorage.setItem(SPIDER_GENERATING_SESSION_KEY, sessionId);
    }
    set({ currentSessionId: sessionId });
  },
  setGenerating: (isGenerating) => {
    const sessionId = useSpiderChatStore.getState().currentSessionId;
    if (isGenerating && sessionId) {
      sessionStorage.setItem(SPIDER_GENERATING_SESSION_KEY, sessionId);
    } else {
      sessionStorage.removeItem(SPIDER_GENERATING_SESSION_KEY);
    }
    set({ isGenerating });
  },
  setLoadingHistory: (isLoadingHistory) => set({ isLoadingHistory }),
  bumpSessionList: () => set((state) => ({ sessionListVersion: state.sessionListVersion + 1 })),
  clearMessages: () => set({ messages: [], workspaceFiles: [] }),
  startNewSession: () => {
    syncActiveSessionId(null);
    sessionStorage.removeItem(SPIDER_DRAFT_TARGET_URL_KEY);
    sessionStorage.removeItem(SPIDER_GENERATING_SESSION_KEY);
    set((state) => ({
      messages: [],
      currentSessionId: null,
      isLoadingHistory: false,
      workspaceFiles: [],
      targetUrl: '',
      restoreInterruptedHint: false,
      sessionEpoch: state.sessionEpoch + 1,
    }));
  },
  setTargetUrl: (targetUrl) => {
    const sessionId = useSpiderChatStore.getState().currentSessionId;
    if (sessionId) {
      if (targetUrl.trim()) {
        sessionStorage.setItem(spiderTargetUrlStorageKey(sessionId), targetUrl);
      } else {
        sessionStorage.removeItem(spiderTargetUrlStorageKey(sessionId));
      }
      sessionStorage.removeItem(SPIDER_DRAFT_TARGET_URL_KEY);
    } else if (targetUrl.trim()) {
      sessionStorage.setItem(SPIDER_DRAFT_TARGET_URL_KEY, targetUrl);
    } else {
      sessionStorage.removeItem(SPIDER_DRAFT_TARGET_URL_KEY);
    }
    set({ targetUrl });
  },
  setWorkspaceFiles: (workspaceFiles) => set({ workspaceFiles }),
  setRestoreInterruptedHint: (restoreInterruptedHint) => set({ restoreInterruptedHint }),
}));
