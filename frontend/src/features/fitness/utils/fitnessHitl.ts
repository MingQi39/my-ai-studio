const CONFIRM_PATTERNS = [
  /^是$/,
  /^是的$/,
  /^好$/,
  /^好的$/,
  /^确认$/,
  /^确定$/,
  /^可以$/,
  /^行$/,
  /^ok$/i,
  /^yes$/i,
  /^confirm$/i,
  /^y$/i,
];

const CANCEL_PATTERNS = [
  /^否$/,
  /^不$/,
  /^不要$/,
  /^不用$/,
  /^取消$/,
  /^算了$/,
  /^no$/i,
  /^cancel$/i,
  /^n$/i,
];

export function isApprovalConfirm(text: string): boolean {
  const normalized = text.trim();
  return CONFIRM_PATTERNS.some((pattern) => pattern.test(normalized));
}

export function isApprovalCancel(text: string): boolean {
  const normalized = text.trim();
  return CANCEL_PATTERNS.some((pattern) => pattern.test(normalized));
}

const WRITE_TOOLS = new Set(['log_meal', 'set_daily_calorie_goal', 'delete_diary_entry']);

export function isWriteTool(toolName: string): boolean {
  return WRITE_TOOLS.has(toolName);
}

export function buildApprovalPreviewFromToolArgs(
  toolName: string,
  toolArgs: Record<string, unknown>,
): import('@/features/fitness/types/hitl').FitnessApprovalPreview {
  if (toolName === 'set_daily_calorie_goal') {
    const goal = Number(toolArgs.daily_calorie_goal ?? 0);
    return {
      kind: 'set_goal',
      daily_calorie_goal: goal,
      previous_daily_calorie_goal: null,
    };
  }

  if (toolName === 'log_meal') {
    const items = Array.isArray(toolArgs.items)
      ? (toolArgs.items as Array<{ name: string; qty?: number; unit?: string; kcal: number; source?: string }>)
      : [];
    const total = items.reduce((sum, item) => sum + Number(item.kcal ?? 0), 0);
    return {
      kind: 'log_meal',
      meal_type: String(toolArgs.meal_type ?? 'lunch'),
      items,
      total_kcal: Math.round(total * 10) / 10,
      note: toolArgs.note as string | null | undefined,
    };
  }

  if (toolName === 'delete_diary_entry') {
    return {
      kind: 'delete_entry',
      entry_id: String(toolArgs.entry_id ?? ''),
    };
  }

  return {
    kind: 'unknown',
    tool_name: toolName,
    tool_args: toolArgs,
  };
}
