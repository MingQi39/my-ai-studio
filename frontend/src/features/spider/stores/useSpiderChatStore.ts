import { create } from 'zustand';

import type { StudioChatMessage } from '@/hooks/studioChat/types';
import type { SpiderWorkspaceFile } from '@/features/spider/services/api/spider';
import {
  SPIDER_ACTIVE_SESSION_KEY,
  SPIDER_DRAFT_TARGET_URL_KEY,
  SPIDER_GENERATING_SESSION_KEY,
  spiderTargetUrlStorageKey,
} from '@/features/spider/constants/session';
import {
  patchGeneratingMessages,
  stashSessionMessages,
  type SpiderMessageCache,
} from '@/features/spider/stores/sessionMessageCache';

function syncActiveSessionId(sessionId: string | null) {
  if (sessionId) {
    sessionStorage.setItem(SPIDER_ACTIVE_SESSION_KEY, sessionId);
  } else {
    sessionStorage.removeItem(SPIDER_ACTIVE_SESSION_KEY);
  }
}

function syncGeneratingSessionId(sessionId: string | null) {
  if (sessionId) {
    sessionStorage.setItem(SPIDER_GENERATING_SESSION_KEY, sessionId);
  } else {
    sessionStorage.removeItem(SPIDER_GENERATING_SESSION_KEY);
  }
}

interface SpiderChatStore {
  messages: StudioChatMessage[];
  messageCache: SpiderMessageCache<StudioChatMessage>;
  currentSessionId: string | null;
  generatingSessionId: string | null;
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
  switchToSession: (sessionId: string) => void;
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
  messageCache: {},
  currentSessionId: null,
  generatingSessionId: null,
  isGenerating: false,
  isLoadingHistory: false,
  sessionListVersion: 0,
  sessionEpoch: 0,
  targetUrl: '',
  workspaceFiles: [],
  restoreInterruptedHint: false,

  addMessage: (message) =>
    set((state) => {
      const messages = [...state.messages, message];
      const sessionKey = state.currentSessionId ?? state.generatingSessionId;
      const messageCache = sessionKey
        ? { ...state.messageCache, [sessionKey]: messages }
        : state.messageCache;
      return { messages, messageCache };
    }),

  updateMessage: (id, updates) =>
    set((state) =>
      patchGeneratingMessages({
        messages: state.messages,
        messageCache: state.messageCache,
        currentSessionId: state.currentSessionId,
        generatingSessionId: state.generatingSessionId,
        messageId: id,
        updates,
      }),
    ),

  setMessages: (messages) =>
    set((state) => {
      const messageCache = state.currentSessionId
        ? { ...state.messageCache, [state.currentSessionId]: messages }
        : state.messageCache;
      return { messages, messageCache };
    }),

  setCurrentSessionId: (sessionId) => {
    syncActiveSessionId(sessionId);
    set((state) => {
      let generatingSessionId = state.generatingSessionId;
      let messageCache = state.messageCache;

      // First SSE session event during a new run: bind generating id to the new session.
      if (state.isGenerating && sessionId && !generatingSessionId) {
        generatingSessionId = sessionId;
        messageCache = { ...messageCache, [sessionId]: state.messages };
        syncGeneratingSessionId(sessionId);
      } else if (generatingSessionId) {
        syncGeneratingSessionId(generatingSessionId);
      }

      return {
        currentSessionId: sessionId,
        generatingSessionId,
        messageCache,
      };
    });
  },

  switchToSession: (sessionId) => {
    syncActiveSessionId(sessionId);
    set((state) => {
      const messageCache = stashSessionMessages(
        state.messageCache,
        state.currentSessionId,
        state.messages,
      );
      return {
        currentSessionId: sessionId,
        messages: messageCache[sessionId] ?? [],
        messageCache,
        restoreInterruptedHint: false,
        workspaceFiles: [],
        isLoadingHistory: false,
      };
    });
  },

  setGenerating: (isGenerating) => {
    set((state) => {
      if (isGenerating) {
        const generatingSessionId = state.currentSessionId;
        syncGeneratingSessionId(generatingSessionId);
        const messageCache =
          generatingSessionId != null
            ? { ...state.messageCache, [generatingSessionId]: state.messages }
            : state.messageCache;
        return { isGenerating: true, generatingSessionId, messageCache };
      }
      syncGeneratingSessionId(null);
      return { isGenerating: false, generatingSessionId: null };
    });
  },

  setLoadingHistory: (isLoadingHistory) => set({ isLoadingHistory }),
  bumpSessionList: () => set((state) => ({ sessionListVersion: state.sessionListVersion + 1 })),
  clearMessages: () => set({ messages: [], workspaceFiles: [] }),
  startNewSession: () => {
    syncActiveSessionId(null);
    sessionStorage.removeItem(SPIDER_DRAFT_TARGET_URL_KEY);
    set((state) => {
      const messageCache = stashSessionMessages(
        state.messageCache,
        state.currentSessionId,
        state.messages,
      );
      if (!state.isGenerating) {
        syncGeneratingSessionId(null);
      }
      return {
        messages: [],
        messageCache,
        currentSessionId: null,
        isLoadingHistory: false,
        workspaceFiles: [],
        targetUrl: '',
        restoreInterruptedHint: false,
        sessionEpoch: state.sessionEpoch + 1,
      };
    });
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
