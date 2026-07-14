import { create } from 'zustand';

import type { StudioChatMessage } from '@/hooks/studioChat/types';
import type { SpiderWorkspaceFile } from '@/features/spider/services/api/spider';
import {
  SPIDER_ACTIVE_SESSION_KEY,
  SPIDER_DRAFT_COOKIES_KEY,
  SPIDER_DRAFT_TARGET_URL_KEY,
  SPIDER_GENERATING_SESSION_KEY,
  spiderCookiesStorageKey,
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

function readStoredCookies(sessionId: string | null): { cookies: string; rememberCookies: boolean } {
  if (sessionId) {
    const stored = sessionStorage.getItem(spiderCookiesStorageKey(sessionId));
    if (stored != null && stored !== '') {
      return { cookies: stored, rememberCookies: true };
    }
    return { cookies: '', rememberCookies: false };
  }
  const draft = sessionStorage.getItem(SPIDER_DRAFT_COOKIES_KEY);
  if (draft != null && draft !== '') {
    return { cookies: draft, rememberCookies: true };
  }
  return { cookies: '', rememberCookies: false };
}

function persistCookies(sessionId: string | null, cookies: string, remember: boolean) {
  const value = cookies.trim();
  if (sessionId) {
    sessionStorage.removeItem(SPIDER_DRAFT_COOKIES_KEY);
    if (remember && value) {
      sessionStorage.setItem(spiderCookiesStorageKey(sessionId), cookies);
    } else {
      sessionStorage.removeItem(spiderCookiesStorageKey(sessionId));
    }
    return;
  }
  if (remember && value) {
    sessionStorage.setItem(SPIDER_DRAFT_COOKIES_KEY, cookies);
  } else {
    sessionStorage.removeItem(SPIDER_DRAFT_COOKIES_KEY);
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
  cookies: string;
  rememberCookies: boolean;
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
  setCookies: (cookies: string) => void;
  setRememberCookies: (remember: boolean) => void;
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
  cookies: '',
  rememberCookies: false,
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

      if (sessionId && state.rememberCookies && state.cookies.trim()) {
        persistCookies(sessionId, state.cookies, true);
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
    const storedCookies = readStoredCookies(sessionId);
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
        cookies: storedCookies.cookies,
        rememberCookies: storedCookies.rememberCookies,
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
    sessionStorage.removeItem(SPIDER_DRAFT_COOKIES_KEY);
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
        cookies: '',
        rememberCookies: false,
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
  setCookies: (cookies) => {
    const { currentSessionId, rememberCookies } = useSpiderChatStore.getState();
    persistCookies(currentSessionId, cookies, rememberCookies);
    set({ cookies });
  },
  setRememberCookies: (rememberCookies) => {
    const { currentSessionId, cookies } = useSpiderChatStore.getState();
    persistCookies(currentSessionId, cookies, rememberCookies);
    set({ rememberCookies });
  },
  setWorkspaceFiles: (workspaceFiles) => set({ workspaceFiles }),
  setRestoreInterruptedHint: (restoreInterruptedHint) => set({ restoreInterruptedHint }),
}));
