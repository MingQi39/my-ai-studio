/**
 * TypeScript 类型定义
 * 已验证：与后端 models.py 和 react_agent.py 实际行为一致
 */

// ============ 基础类型 ============

export type EventType =
  | "start"
  | "done"
  | "chunk"
  | "round_start"
  | "round_end"
  | "step"
  | "tool_call_start"
  | "tool_call_result"
  | "stats_update"
  | "final_response"
  | "error"
  | "session"

export type StepType = "Observe" | "Think" | "Act" | "Verify"

export type Source = "llm" | "agent"

// ============ 统计信息 ============

export interface ExecutionStats {
  llm_calls: number
  tool_calls: number
  duration_ms: number
  tokens_used?: number
}

// ============ SSE 事件基础接口 ============

export interface BaseSSEEvent {
  type: EventType
  source: Source
  timestamp: string
  sequence?: number
}

// ============ 具体事件类型 ============

export interface StartEvent extends BaseSSEEvent {
  type: "start"
}

export interface DoneEvent extends BaseSSEEvent {
  type: "done"
  stats?: ExecutionStats
}

export interface ChunkEvent extends BaseSSEEvent {
  type: "chunk"
  content: string
}

export interface RoundStartEvent extends BaseSSEEvent {
  type: "round_start"
  round: number
}

export interface RoundEndEvent extends BaseSSEEvent {
  type: "round_end"
  round: number
}

export interface StepEvent extends BaseSSEEvent {
  type: "step"
  step_type: StepType
  round: number
  content: string
}

export interface ToolCallStartEvent extends BaseSSEEvent {
  type: "tool_call_start"
  tool_name: string
  tool_args: Record<string, any>
  call_id: string
}

export interface ToolCallResultEvent extends BaseSSEEvent {
  type: "tool_call_result"
  tool_name: string
  result: string
  status: "success" | "error"
  duration_ms: number
  call_id: string
  error?: string
}

export interface StatsUpdateEvent extends BaseSSEEvent {
  type: "stats_update"
  stats: ExecutionStats
}

export interface ErrorEvent extends BaseSSEEvent {
  type: "error"
  error_type: string
  message: string
  recoverable?: boolean
  context?: Record<string, any>
}

export interface FinalResponseEvent extends BaseSSEEvent {
  type: "final_response"
  content: string
}

export interface SessionEvent {
  type: "session"
  session_id: string
  created?: boolean
}

// ============ 联合类型 ============

export type SSEEvent =
  | StartEvent
  | DoneEvent
  | ChunkEvent
  | RoundStartEvent
  | RoundEndEvent
  | StepEvent
  | ToolCallStartEvent
  | ToolCallResultEvent
  | StatsUpdateEvent
  | FinalResponseEvent
  | ErrorEvent
  | SessionEvent
