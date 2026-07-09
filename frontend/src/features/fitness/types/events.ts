import type { FitnessApprovalPreview } from '@/features/fitness/types/hitl';

export type FitnessSSEEvent =
  | { type: 'session'; source?: string; session_id: string; created: boolean }
  | { type: 'start'; source?: string }
  | {
      type: 'tool_call_start';
      source?: string;
      call_id: string;
      tool_name: string;
      tool_args: Record<string, unknown>;
    }
  | {
      type: 'tool_call_result';
      source?: string;
      call_id: string;
      result: any;
      status: 'success' | 'error' | 'pending_approval';
      duration_ms?: number;
      error?: string;
    }
  | {
      type: 'tool_progress';
      source?: string;
      call_id: string;
      tool_name: string;
      stage: string;
      food_name?: string;
      index?: number;
      total?: number;
    }
  | { type: 'chunk'; source?: string; content?: string }
  | { type: 'final_response'; source?: string; content?: string }
  | { type: 'meal_logged'; source?: string; entry: any }
  | { type: 'recommendations'; source?: string; recommendations: any[] }
  | {
      type: 'approval_required';
      source?: string;
      call_id: string;
      tool_name: string;
      tool_args: Record<string, unknown>;
      preview: FitnessApprovalPreview;
    }
  | { type: 'error'; source?: string; error_type?: string; message?: string; recoverable?: boolean }
  | { type: 'done'; source?: string };

