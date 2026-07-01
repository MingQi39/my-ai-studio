/**
 * ChatView 状态管理
 * 使用 Zustand 管理聊天消息和生成状态
 */

import { create } from 'zustand'

import type { ReActStep } from '@/features/travel/types/react'
import type { TravelPlanGenerateResponse } from '@/features/travel/types/itinerary'

export type { ReActStep, ToolCall } from '@/features/travel/types/react'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  mode?: 'llm' | 'agent'
  thinkingSteps?: ReActStep[]
  timestamp: number
}

export interface FormalPlanCache {
  sessionId: string
  fingerprint: string
  isStale?: boolean
  result: TravelPlanGenerateResponse
}

interface ChatStore {
  messages: Message[]
  currentSessionId: string | null
  formalPlanCache: FormalPlanCache | null
  isGenerating: boolean
  isLoadingHistory: boolean
  sessionListVersion: number
  sessionEpoch: number
  chatMode: 'llm' | 'agent'
  addMessage: (message: Message) => void
  updateMessage: (id: string, updates: Partial<Message>) => void
  setMessages: (messages: Message[]) => void
  setCurrentSessionId: (sessionId: string | null) => void
  setFormalPlanCache: (cache: FormalPlanCache | null) => void
  setGenerating: (generating: boolean) => void
  setLoadingHistory: (loading: boolean) => void
  bumpSessionList: () => void
  setChatMode: (mode: 'llm' | 'agent') => void
  clearMessages: () => void
  startNewSession: () => void
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  currentSessionId: null,
  formalPlanCache: null,
  isGenerating: false,
  isLoadingHistory: false,
  sessionListVersion: 0,
  sessionEpoch: 0,
  chatMode: 'agent',
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),
  updateMessage: (id, updates) => set((state) => ({
    messages: state.messages.map(msg =>
      msg.id === id ? { ...msg, ...updates } : msg
    )
  })),
  setMessages: (messages) => set({ messages }),
  setCurrentSessionId: (sessionId) => set((state) => ({
    currentSessionId: sessionId,
    formalPlanCache:
      sessionId && state.formalPlanCache?.sessionId === sessionId
        ? state.formalPlanCache
        : null,
  })),
  setFormalPlanCache: (formalPlanCache) => set({ formalPlanCache }),
  setGenerating: (generating) => set({ isGenerating: generating }),
  setLoadingHistory: (loading) => set({ isLoadingHistory: loading }),
  bumpSessionList: () => set((state) => ({ sessionListVersion: state.sessionListVersion + 1 })),
  setChatMode: (mode) => set({ chatMode: mode }),
  clearMessages: () => set({ messages: [], formalPlanCache: null }),
  startNewSession: () => set((state) => ({
    messages: [],
    currentSessionId: null,
    formalPlanCache: null,
    isLoadingHistory: false,
    sessionEpoch: state.sessionEpoch + 1,
  })),
}))
