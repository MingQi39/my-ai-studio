import { useState } from 'react';
import { Check, ListTodo, Loader2, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/components/ui/utils';
import type { SpiderTodoItem } from '@/features/spider/types/todo';

type SpiderTodoCardProps = {
  todos: SpiderTodoItem[];
  isDarkMode?: boolean;
};

export function SpiderTodoCard({ todos, isDarkMode = false }: SpiderTodoCardProps) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);

  if (todos.length === 0) return null;

  const completed = todos.filter((item) => item.status === 'completed').length;
  const total = todos.length;

  return (
    <div
      className={cn(
        'rounded-xl border border-[var(--border-color)] shadow-sm overflow-hidden',
        isDarkMode ? 'bg-slate-900/60' : 'bg-slate-50',
      )}
    >
      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2 text-sm text-[var(--text-primary)]">
          <ListTodo size={16} className="shrink-0 text-violet-500" />
          <span className="truncate font-medium">
            {t('spider.chat.todos.completedCount', { completed, total })}
          </span>
        </div>
        <button
          type="button"
          className="shrink-0 rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]"
          aria-label={collapsed ? t('spider.chat.todos.expand') : t('spider.chat.todos.collapse')}
          onClick={() => setCollapsed((v) => !v)}
        >
          {collapsed ? <ListTodo size={14} /> : <X size={14} />}
        </button>
      </div>

      {!collapsed && (
        <ul className="max-h-48 space-y-1.5 overflow-y-auto border-t border-[var(--border-color)] px-3 py-2">
          {todos.map((todo, index) => {
            const isDone = todo.status === 'completed';
            const isFailed = todo.status === 'failed';
            const isRunning = todo.status === 'in_progress';
            return (
              <li key={`${index}-${todo.content}`} className="flex min-w-0 items-center gap-2">
                <span className="shrink-0">
                  {isDone ? (
                    <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-white">
                      <Check size={10} strokeWidth={3} />
                    </span>
                  ) : isFailed ? (
                    <span
                      className="flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-white"
                      aria-label={t('spider.chat.todos.failed')}
                    >
                      <X size={10} strokeWidth={3} />
                    </span>
                  ) : isRunning ? (
                    <Loader2
                      size={16}
                      className="animate-spin text-slate-400"
                      aria-label={t('spider.chat.todos.inProgress')}
                    />
                  ) : (
                    <span className="block h-4 w-4 rounded-full border border-slate-300" />
                  )}
                </span>
                <span
                  className={cn(
                    'min-w-0 flex-1 truncate text-sm',
                    isDone
                      ? 'text-[var(--text-secondary)] line-through'
                      : isFailed
                        ? 'text-red-600'
                        : 'text-[var(--text-primary)]',
                  )}
                  title={todo.content}
                >
                  {todo.content}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
