import { create } from 'zustand';

import type { StudioChatMessage } from '@/hooks/studioChat/types';
import type { FitnessGuidedFlowId, FitnessPendingApproval } from '@/features/fitness/types/hitl';

export interface FitnessTodaySummary {
  date: string;
  daily_calorie_goal: number;
  consumed_kcal: number;
  remaining_kcal: number;
  entries: Array<{
    id: string;
    meal_type: string;
    items: Array<{ name: string; qty: number; unit: string; kcal: number; source: string }>;
    total_kcal: number;
    note?: string | null;
    session_id?: string | null;
  }>;
  disclaimer: string;
}

interface FitnessChatStore {
  messages: StudioChatMessage[];
  currentSessionId: string | null;
  isGenerating: boolean;
  isLoadingHistory: boolean;
  sessionListVersion: number;
  sessionEpoch: number;
  recommendations: any[]; // v1
  todaySummary: FitnessTodaySummary | null;
  guidedFlow: FitnessGuidedFlowId | null;
  pendingApproval: FitnessPendingApproval | null;

  addMessage: (message: StudioChatMessage) => void;
  updateMessage: (id: string, updates: Partial<StudioChatMessage>) => void;
  setMessages: (messages: StudioChatMessage[]) => void;
  setCurrentSessionId: (sessionId: string | null) => void;
  setGenerating: (generating: boolean) => void;
  setLoadingHistory: (loading: boolean) => void;
  bumpSessionList: () => void;
  clearMessages: () => void;
  startNewSession: () => void;

  setRecommendations: (recs: any[]) => void;
  setTodaySummary: (summary: FitnessTodaySummary | null) => void;
  setGuidedFlow: (flow: FitnessGuidedFlowId | null) => void;
  setPendingApproval: (approval: FitnessPendingApproval | null) => void;
}

export const useFitnessChatStore = create<FitnessChatStore>((set) => ({
  messages: [],
  currentSessionId: null,
  isGenerating: false,
  isLoadingHistory: false,
  sessionListVersion: 0,
  sessionEpoch: 0,
  recommendations: [],
  todaySummary: null,
  guidedFlow: null,
  pendingApproval: null,

  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),

  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((msg) => (msg.id === id ? { ...msg, ...updates } : msg)),
    })),

  setMessages: (messages) => set({ messages }),

  setCurrentSessionId: (sessionId) => set({ currentSessionId: sessionId }),
  setGenerating: (isGenerating) => set({ isGenerating }),
  setLoadingHistory: (isLoadingHistory) => set({ isLoadingHistory }),
  bumpSessionList: () => set((state) => ({ sessionListVersion: state.sessionListVersion + 1 })),
  clearMessages: () => set({ messages: [], recommendations: [], guidedFlow: null, pendingApproval: null }),
  startNewSession: () =>
    set((state) => ({
      messages: [],
      currentSessionId: null,
      isLoadingHistory: false,
      isGenerating: false,
      recommendations: [],
      guidedFlow: null,
      pendingApproval: null,
      sessionEpoch: state.sessionEpoch + 1,
    })),

  setRecommendations: (recommendations) => set({ recommendations }),
  setTodaySummary: (todaySummary) => set({ todaySummary }),
  setGuidedFlow: (guidedFlow) => set({ guidedFlow }),
  setPendingApproval: (pendingApproval) => set({ pendingApproval }),
}));

