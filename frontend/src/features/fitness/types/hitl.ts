export type FitnessGuidedFlowId = 'logLunch' | 'recommend' | 'setGoal';

export type FitnessApprovalPreview =
  | {
      kind: 'set_goal';
      daily_calorie_goal: number;
      previous_daily_calorie_goal?: number | null;
    }
  | {
      kind: 'log_meal';
      meal_type: string;
      items: Array<{ name: string; qty?: number; unit?: string; kcal: number; source?: string }>;
      total_kcal: number;
      note?: string | null;
    }
  | {
      kind: 'delete_entry';
      entry_id: string;
    }
  | {
      kind: 'unknown';
      tool_name?: string;
      tool_args?: Record<string, unknown>;
    };

export type FitnessPendingApproval = {
  callId: string;
  toolName: string;
  toolArgs: Record<string, unknown>;
  preview: FitnessApprovalPreview;
  assistantMessageId: string;
};
