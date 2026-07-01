/**
 * ReactView 状态管理
 * 使用 Zustand 管理 ReAct 步骤和执行状态
 */

import { create } from 'zustand'
import type { StepType, ExecutionStats } from '@/types/events'

export interface ToolCall {
  id: string
  tool_name: string
  tool_args: Record<string, any>
  result?: string
  status?: 'pending' | 'success' | 'error'
  duration_ms?: number
  error?: string
}

export interface ReActStep {
  type: StepType
  content: string
  round: number
  sequence: number
  toolCalls?: ToolCall[]
}

interface ReActStore {
  steps: ReActStep[]
  simulationState: 'idle' | 'loading' | 'done' | 'error'
  stats: ExecutionStats | null
  errorMessage: string | null
  addStep: (step: ReActStep) => void
  updateStepToolCalls: (sequence: number, toolCalls: ToolCall[]) => void
  setSimulationState: (state: 'idle' | 'loading' | 'done' | 'error') => void
  setStats: (stats: ExecutionStats) => void
  setError: (message: string) => void
  reset: () => void
}

export const useReactStore = create<ReActStore>((set) => ({
  steps: [],
  simulationState: 'idle',
  stats: null,
  errorMessage: null,
  addStep: (step) => set((state) => ({
    steps: [...state.steps, step]
  })),
  updateStepToolCalls: (sequence, toolCalls) => set((state) => ({
    steps: state.steps.map(step =>
      step.sequence === sequence
        ? { ...step, toolCalls }
        : step
    )
  })),
  setSimulationState: (state) => set({ simulationState: state }),
  setStats: (stats) => set({ stats }),
  setError: (message) => set({ errorMessage: message, simulationState: 'error' }),
  reset: () => set({
    steps: [],
    simulationState: 'idle',
    stats: null,
    errorMessage: null
  })
}))
