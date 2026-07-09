import { useState } from 'react';
import { ChevronDown, ChevronRight, GripVertical, Pencil, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/components/ui/utils';

export type MessageQueuePanelProps<T> = {
  queue: Array<{ id: string; payload: T }>;
  getLabel: (payload: T) => string;
  onRemove: (id: string) => void;
  onEdit?: (id: string, payload: T) => void;
  onReorder?: (activeId: string, overId: string) => void;
  className?: string;
};

export function MessageQueuePanel<T>({
  queue,
  getLabel,
  onRemove,
  onEdit,
  onReorder,
  className,
}: MessageQueuePanelProps<T>) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(true);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  const canReorder = !!onReorder && queue.length > 1;

  if (queue.length === 0) {
    return null;
  }

  const finishDrag = () => {
    setDraggingId(null);
    setOverId(null);
  };

  const handleDrop = (targetId: string) => (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const activeId = draggingId ?? event.dataTransfer.getData('text/plain');
    if (activeId && activeId !== targetId) {
      onReorder?.(activeId, targetId);
    }
    finishDrag();
  };

  return (
    <div
      className={cn(
        'rounded-xl border border-slate-200/80 dark:border-slate-700/80 bg-slate-50/90 dark:bg-slate-900/70 overflow-hidden',
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100/80 dark:hover:bg-slate-800/60 transition-colors"
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span>{t('chat.queue.count', { count: queue.length })}</span>
        {canReorder && expanded && (
          <span className="ml-auto text-[10px] font-normal text-slate-400 dark:text-slate-500">
            {t('chat.queue.dragHint')}
          </span>
        )}
      </button>

      {expanded && (
        <div className="px-2 pb-2 space-y-1.5">
          {queue.map((item) => {
            const isDragging = draggingId === item.id;
            const isOver = overId === item.id && draggingId !== item.id;

            return (
              <div
                key={item.id}
                onDragOver={(event) => {
                  if (!canReorder || !draggingId || draggingId === item.id) return;
                  event.preventDefault();
                  event.dataTransfer.dropEffect = 'move';
                  setOverId(item.id);
                }}
                onDragLeave={() => {
                  if (overId === item.id) {
                    setOverId(null);
                  }
                }}
                onDrop={handleDrop(item.id)}
                className={cn(
                  'group flex items-start gap-1.5 rounded-lg border bg-white/90 dark:bg-slate-800/80 px-2 py-2 transition-all',
                  isDragging && 'opacity-40 scale-[0.98]',
                  isOver
                    ? 'border-blue-400 dark:border-blue-500 ring-1 ring-blue-400/40'
                    : 'border-slate-200/70 dark:border-slate-700/70',
                )}
              >
                {canReorder && (
                  <button
                    type="button"
                    draggable
                    onDragStart={(event) => {
                      setDraggingId(item.id);
                      event.dataTransfer.effectAllowed = 'move';
                      event.dataTransfer.setData('text/plain', item.id);
                    }}
                    onDragEnd={finishDrag}
                    className="mt-0.5 p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:text-slate-300 dark:hover:bg-slate-700 cursor-grab active:cursor-grabbing touch-none shrink-0"
                    aria-label={t('chat.queue.dragHandle')}
                  >
                    <GripVertical size={14} />
                  </button>
                )}
                <p className="flex-1 text-sm text-slate-700 dark:text-slate-200 whitespace-pre-wrap break-words line-clamp-3">
                  {getLabel(item.payload)}
                </p>
                <div className="flex items-center gap-0.5 shrink-0 opacity-80 group-hover:opacity-100">
                  {onEdit && (
                    <button
                      type="button"
                      onClick={() => onEdit(item.id, item.payload)}
                      className="p-1.5 rounded-md text-slate-500 hover:text-slate-700 hover:bg-slate-100 dark:hover:text-slate-200 dark:hover:bg-slate-700 transition-colors"
                      aria-label={t('chat.queue.edit')}
                    >
                      <Pencil size={13} />
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onRemove(item.id)}
                    className="p-1.5 rounded-md text-slate-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors"
                    aria-label={t('chat.queue.remove')}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
