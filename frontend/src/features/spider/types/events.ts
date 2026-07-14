export type SpiderSSEEvent =
  | { type: 'session'; source?: string; session_id: string; created: boolean }
  | { type: 'start'; source?: string }
  | {
      type: 'tool_call_start';
      source?: string;
      call_id: string;
      tool_name: string;
      tool_args: Record<string, unknown>;
      raw_tool_name?: string;
    }
  | {
      type: 'tool_call_result';
      source?: string;
      call_id: string;
      tool_name?: string;
      result: unknown;
      status: 'success' | 'error';
    }
  | {
      type: 'subagent_start';
      source?: string;
      call_id: string;
      subagent?: string;
      description?: string;
    }
  | {
      type: 'subagent_complete';
      source?: string;
      call_id: string;
      result_preview?: string;
    }
  | { type: 'chunk'; source?: string; content?: string }
  | { type: 'final_response'; source?: string; content?: string }
  | {
      type: 'workspace_updated';
      source?: string;
      workspace_path?: string;
      volume_name?: string;
      files?: Array<{ name: string; size: number; modified_at?: string | null }>;
    }
  | {
      type: 'todos_updated';
      source?: string;
      todos: Array<{ content: string; status: 'pending' | 'in_progress' | 'completed' }>;
    }
  | {
      type: 'error';
      source?: string;
      message?: string;
      code?: string;
      title?: string;
      detail?: string;
      hints?: string[];
      stage?: string;
      recoverable?: boolean;
    }
  | { type: 'done'; source?: string };
