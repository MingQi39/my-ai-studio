import type { StepType } from '@/features/travel/types/events';

export interface ToolCall {
  id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  result?: string;
  status?: 'pending' | 'success' | 'error';
  duration_ms?: number;
  error?: string;
}

export interface ReActStep {
  type: StepType;
  content: string;
  round: number;
  sequence: number;
  toolCalls?: ToolCall[];
}
