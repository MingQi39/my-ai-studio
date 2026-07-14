export type SpiderTodoStatus = 'pending' | 'in_progress' | 'completed';

export type SpiderTodoItem = {
  content: string;
  status: SpiderTodoStatus;
};

export function isSpiderTodoStatus(value: unknown): value is SpiderTodoStatus {
  return value === 'pending' || value === 'in_progress' || value === 'completed';
}

export function normalizeSpiderTodos(raw: unknown): SpiderTodoItem[] {
  if (!Array.isArray(raw)) return [];
  const result: SpiderTodoItem[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const content = (item as { content?: unknown }).content;
    const status = (item as { status?: unknown }).status;
    if (typeof content !== 'string' || !content.trim()) continue;
    if (!isSpiderTodoStatus(status)) continue;
    result.push({ content: content.trim(), status });
  }
  return result;
}
