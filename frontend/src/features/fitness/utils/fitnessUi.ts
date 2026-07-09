export type CalorieSource = 'local' | 'usda' | 'estimate' | string;

export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack' | string;

export function formatKcal(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return Math.round(value).toLocaleString();
}

export function mealTypeKey(mealType: MealType): string {
  const key = mealType?.toLowerCase?.() ?? '';
  if (['breakfast', 'lunch', 'dinner', 'snack'].includes(key)) return key;
  return 'other';
}

export const SOURCE_STYLES: Record<
  string,
  { className: string; dotClassName: string }
> = {
  local: {
    className:
      'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20',
    dotClassName: 'bg-emerald-500',
  },
  usda: {
    className: 'bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-500/20',
    dotClassName: 'bg-sky-500',
  },
  web: {
    className: 'bg-violet-500/10 text-violet-700 dark:text-violet-300 border border-violet-500/20',
    dotClassName: 'bg-violet-500',
  },
  estimate: {
    className:
      'bg-amber-500/10 text-amber-800 dark:text-amber-200 border border-amber-500/25',
    dotClassName: 'bg-amber-500',
  },
};

export function sourceStyle(source: CalorieSource) {
  return SOURCE_STYLES[source] ?? SOURCE_STYLES.estimate;
}

export const FITNESS_TOOL_LABELS: Record<string, string> = {
  resolve_food_calories: '解析热量',
  get_today_summary: '查询今日',
  set_daily_calorie_goal: '更新目标',
  log_meal: '写入日记',
  delete_diary_entry: '删除记录',
  recommend_meals: '生成推荐',
};
