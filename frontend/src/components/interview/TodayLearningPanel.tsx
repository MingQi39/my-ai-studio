import { useEffect, useRef, useState } from 'react';
import { BookOpen, CheckCircle2, History, Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { LearningDocWorkspace } from '@/components/interview/LearningDocWorkspace';
import {
  getInterviewLearningDocByDate,
  listInterviewLearningDocs,
  setInterviewLearningDayStatus,
  type InterviewTodayPlan,
  type LearningDocHistoryItem,
  type TodayLearningDoc,
} from '@/services/api';

type TodayLearningPanelProps = {
  todayPlan: InterviewTodayPlan | null;
  loading?: boolean;
  onPractice?: (topic: string) => void;
  /** compact = sidebar teaser; full = inline block */
  variant?: 'compact' | 'full';
  onOpenFull?: () => void;
};

export function TodayLearningCompactCard({
  todayPlan,
  loading,
  onOpenFull,
}: Pick<TodayLearningPanelProps, 'todayPlan' | 'loading' | 'onOpenFull'>) {
  const doc = todayPlan?.learning_doc;
  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-[var(--border-color)] p-3 text-[11px] text-[var(--text-secondary)]">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        加载今日学习文档…
      </div>
    );
  }
  if (!doc) return null;

  const status = todayPlan?.learning_status;
  const backlog = Boolean(todayPlan?.is_backlog);
  const packed = todayPlan?.units_packed || 1;

  return (
    <button
      type="button"
      onClick={onOpenFull}
      className="w-full rounded-xl border border-amber-500/30 bg-amber-500/5 p-3.5 text-left transition hover:border-amber-500/50 active:bg-amber-500/10"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[10px] font-medium tracking-wide text-amber-700 dark:text-amber-300">
          <BookOpen className="h-3.5 w-3.5" />
          {backlog ? '待完成学习' : '今日学习'}
        </div>
        <span className="text-[10px] text-[var(--text-secondary)]">
          {status === 'completed' ? '已完成' : backlog ? '未完成' : doc.generated_by === 'llm' ? 'AI' : '模板'}
        </span>
      </div>
      <p className="mt-1.5 text-sm font-semibold text-[var(--text-primary)]">{doc.section_title}</p>
      {backlog && todayPlan?.active_date && (
        <p className="mt-1 text-[11px] text-amber-800 dark:text-amber-200">
          仍卡在 {todayPlan.active_date} · 完成前不会推送新内容
          {(todayPlan.incomplete_count || 0) > 1 ? `（积压 ${todayPlan.incomplete_count} 天）` : ''}
        </p>
      )}
      {packed > 1 && (
        <p className="mt-1 text-[10px] text-[var(--text-secondary)]">加密日 · 今日合并 {packed} 个知识点包</p>
      )}
      <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-[var(--text-secondary)]">
        {doc.today_goal || doc.reading_bullets[0] || doc.doc_title}
      </p>
      <p className="mt-2 text-[10px] font-medium text-amber-700 dark:text-amber-300">
        打开讲义（讲解 · 题目 · 答案）→
      </p>
    </button>
  );
}

export function TodayLearningDialog({
  open,
  onOpenChange,
  todayPlan,
  loading,
  onPractice,
  onRefresh,
  onStatusChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  todayPlan: InterviewTodayPlan | null;
  loading?: boolean;
  onPractice?: (topic: string) => void;
  onRefresh?: () => void;
  onStatusChange?: () => void;
}) {
  const doc = todayPlan?.learning_doc;
  const [statusBusy, setStatusBusy] = useState(false);
  const activeDate = todayPlan?.active_date || todayPlan?.date || null;
  const completed = todayPlan?.learning_status === 'completed';

  const toggleComplete = async () => {
    if (!activeDate) return;
    setStatusBusy(true);
    try {
      await setInterviewLearningDayStatus(activeDate, completed ? 'pending' : 'completed');
      onStatusChange?.();
      onRefresh?.();
    } finally {
      setStatusBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[min(92dvh,92vh)] max-h-[min(92dvh,92vh)] w-[calc(100%-1rem)] max-w-5xl flex-col gap-0 overflow-hidden p-0 sm:w-full sm:max-w-5xl [&>button]:z-20">
        <DialogHeader className="min-w-0 shrink-0 space-y-0 border-b border-[var(--border-color)] px-4 pb-3 pt-5 pr-12 text-left sm:px-6 sm:pb-4 sm:pt-6 sm:pr-14">
          <DialogTitle className="flex flex-wrap items-center gap-2 text-left text-base sm:text-lg">
            <BookOpen className="h-5 w-5 shrink-0 text-amber-600" />
            今日学习讲义
            {todayPlan?.date ? (
              <span className="text-sm font-normal text-[var(--text-secondary)]">· {todayPlan.date}</span>
            ) : null}
          </DialogTitle>
          {doc && (
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <p className="min-w-0 text-left text-sm text-[var(--text-secondary)]">
                <span className="break-words">
                  {doc.doc_title} · {doc.section_title}
                </span>
                <span className="ml-2 inline-block rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[11px] text-amber-800 dark:text-amber-200">
                  {doc.generated_by === 'llm' ? 'AI 讲义' : '模板讲义'}
                </span>
                {todayPlan?.is_backlog && (
                  <span className="ml-2 inline-block rounded-md bg-red-500/10 px-1.5 py-0.5 text-[11px] text-red-700 dark:text-red-300">
                    未完成积压
                  </span>
                )}
                {completed && (
                  <span className="ml-2 inline-block rounded-md bg-emerald-500/10 px-1.5 py-0.5 text-[11px] text-emerald-700 dark:text-emerald-300">
                    已完成
                  </span>
                )}
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={statusBusy || !activeDate}
                  onClick={() => void toggleComplete()}
                  className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-[11px] disabled:opacity-50 ${
                    completed
                      ? 'border-[var(--border-color)] text-[var(--text-secondary)]'
                      : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200'
                  }`}
                >
                  {statusBusy ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3 w-3" />
                  )}
                  {completed ? '标为未完成' : '标为已完成'}
                </button>
                {onRefresh && (
                  <button
                    type="button"
                    disabled={loading}
                    onClick={onRefresh}
                    className="rounded-lg border border-[var(--border-color)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:opacity-50"
                  >
                    {loading ? '生成中…' : '重新生成'}
                  </button>
                )}
              </div>
            </div>
          )}
        </DialogHeader>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-[var(--text-secondary)]">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在生成「讲解 + 题目 + 答案」学习讲义…
            </div>
          )}
          {!loading && !doc && (
            <p className="px-4 py-12 text-center text-sm text-[var(--text-secondary)]">
              请先在目标设置中填写「目标达成时间」，系统会按截止日期生成每日学习讲义（含问题、答案与讲解）。
            </p>
          )}
          {!loading && doc && (
            <LearningDocWorkspace
              doc={doc}
              docDate={activeDate}
              banner={
                todayPlan?.is_backlog ? (
                  <p className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2.5 text-[12.5px] leading-relaxed text-amber-900 dark:text-amber-100">
                    当前展示的是未完成日 {todayPlan.active_date}{' '}
                    的讲义。完成前不会推送新内容；点「标为已完成」后才会解锁后续日程。
                  </p>
                ) : null
              }
              onPractice={
                onPractice
                  ? (topic) => {
                      onOpenChange(false);
                      onPractice(topic);
                    }
                  : undefined
              }
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function TodayLearningHeaderButton({
  todayPlan,
  loading,
  onClick,
}: {
  todayPlan: InterviewTodayPlan | null;
  loading?: boolean;
  onClick: () => void;
}) {
  const doc = todayPlan?.learning_doc;
  const label = doc?.section_title || doc?.topic || '今日学习';

  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-sm font-medium text-amber-900 hover:bg-amber-500/20 dark:text-amber-100"
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BookOpen className="h-3.5 w-3.5" />}
      <span className="max-w-[5rem] truncate sm:max-w-[8rem]">{label}</span>
    </button>
  );
}

export function HistoryLearningHeaderButton({
  onClick,
}: {
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-color)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] sm:px-3"
      title="查看往日推送讲义"
    >
      <History className="h-3.5 w-3.5" />
      <span className="hidden sm:inline">历史讲义</span>
    </button>
  );
}

export function HistoryLearningEntryCard({ onOpen }: { onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex min-h-11 w-full items-center justify-between rounded-xl border border-[var(--border-color)] px-3 py-3 text-left transition hover:bg-[var(--bg-hover)] active:bg-[var(--bg-hover)]"
    >
      <div className="flex items-center gap-2">
        <History className="h-3.5 w-3.5 text-[var(--text-secondary)]" />
        <div>
          <p className="text-[12px] font-medium text-[var(--text-primary)]">历史讲义</p>
          <p className="text-[10px] text-[var(--text-secondary)]">回看往日推送的学习文档</p>
        </div>
      </div>
      <span className="text-[10px] text-amber-700 dark:text-amber-300">打开 →</span>
    </button>
  );
}

export function HistoryLearningDialog({
  open,
  onOpenChange,
  onPractice,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPractice?: (topic: string) => void;
}) {
  const [items, setItems] = useState<LearningDocHistoryItem[]>([]);
  const [hasPlan, setHasPlan] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [doc, setDoc] = useState<TodayLearningDoc | null>(null);
  const [docLoading, setDocLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadSeq = useRef(0);

  const loadList = async () => {
    setListLoading(true);
    setError(null);
    try {
      const hist = await listInterviewLearningDocs();
      setItems(hist.items);
      setHasPlan(hist.has_plan);
      setSelectedDate((prev) => {
        if (prev && hist.items.some((i) => i.date === prev && i.has_doc)) return prev;
        const withDoc = hist.items.find((i) => i.has_doc);
        if (withDoc) return withDoc.date;
        if (prev && hist.items.some((i) => i.date === prev)) return prev;
        return hist.items[0]?.date ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载历史讲义失败');
    } finally {
      setListLoading(false);
    }
  };

  const loadDoc = async (isoDate: string, opts?: { refresh?: boolean; isGenerate?: boolean }) => {
    const seq = ++loadSeq.current;
    setDocLoading(true);
    setGenerating(Boolean(opts?.isGenerate || opts?.refresh));
    setError(null);
    if (opts?.isGenerate || opts?.refresh) setDoc(null);
    try {
      const result = await getInterviewLearningDocByDate(isoDate, opts);
      if (seq !== loadSeq.current) return;
      setDoc(result.learning_doc);
      setItems((prev) =>
        prev.map((item) =>
          item.date === isoDate
            ? {
                ...item,
                has_doc: true,
                generated_by: result.learning_doc.generated_by ?? item.generated_by,
                section_title: result.learning_doc.section_title || item.section_title,
              }
            : item,
        ),
      );
    } catch (err) {
      if (seq !== loadSeq.current) return;
      setDoc(null);
      setError(err instanceof Error ? err.message : '加载讲义失败');
    } finally {
      if (seq === loadSeq.current) {
        setDocLoading(false);
        setGenerating(false);
      }
    }
  };

  useEffect(() => {
    if (!open) {
      loadSeq.current += 1;
      setDocLoading(false);
      setGenerating(false);
      return;
    }
    void loadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open || !selectedDate || listLoading) return;
    const item = items.find((i) => i.date === selectedDate);
    if (!item) {
      setDoc(null);
      return;
    }
    // 无缓存时不自动生成（LLM 可能要一两分钟），避免一直转圈
    if (!item.has_doc) {
      loadSeq.current += 1;
      setDoc(null);
      setDocLoading(false);
      setGenerating(false);
      setError(null);
      return;
    }
    void loadDoc(selectedDate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, selectedDate, listLoading]);

  const selected = items.find((i) => i.date === selectedDate) || null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[min(92dvh,92vh)] max-h-[min(92dvh,92vh)] w-[calc(100%-1rem)] max-w-6xl flex-col gap-0 overflow-hidden p-0 sm:w-full sm:max-w-6xl [&>button]:z-20">
        <DialogHeader className="min-w-0 shrink-0 space-y-0 border-b border-[var(--border-color)] px-4 pb-3 pt-5 pr-12 text-left sm:px-6 sm:pb-4 sm:pt-6 sm:pr-14">
          <DialogTitle className="flex items-center gap-2 text-left text-base sm:text-lg">
            <History className="h-5 w-5 shrink-0 text-amber-600" />
            历史讲义
          </DialogTitle>
          <p className="mt-1 text-left text-sm text-[var(--text-secondary)]">
            按日期回看往日推送；手机可点底部「点选一段提问」
          </p>
        </DialogHeader>

        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden md:flex-row">
          <aside className="min-w-0 shrink-0 border-b border-[var(--border-color)] md:max-h-none md:w-52 md:overflow-y-auto md:border-b-0 md:border-r lg:w-56">
            {listLoading && (
              <div className="flex items-center gap-2 px-4 py-6 text-[12px] text-[var(--text-secondary)]">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                加载列表…
              </div>
            )}
            {!listLoading && !hasPlan && (
              <p className="px-4 py-6 text-[12px] leading-relaxed text-[var(--text-secondary)]">
                还没有学习计划。请先设置目标达成时间。
              </p>
            )}
            {!listLoading && hasPlan && items.length === 0 && (
              <p className="px-4 py-6 text-[12px] leading-relaxed text-[var(--text-secondary)]">
                还没有已生成的讲义。打开「今日学习」生成后会出现在这里。
              </p>
            )}
            <ul className="flex gap-2 overflow-x-auto p-2 md:block md:overflow-x-visible md:overflow-y-auto">
              {items.map((item) => {
                const active = item.date === selectedDate;
                return (
                  <li key={item.date} className="shrink-0 md:w-full md:shrink">
                    <button
                      type="button"
                      onClick={() => setSelectedDate(item.date)}
                      className={`w-full min-w-[9.5rem] rounded-lg px-3 py-2 text-left transition md:min-w-0 ${
                        active
                          ? 'bg-amber-500/15 text-amber-900 dark:text-amber-100'
                          : 'hover:bg-[var(--bg-hover)]'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[12px] font-medium tabular-nums">{item.date}</span>
                        {item.is_today ? (
                          <span className="text-[9px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
                            今天
                          </span>
                        ) : item.is_active ? (
                          <span className="text-[9px] font-semibold tracking-wide text-amber-700 dark:text-amber-300">
                            积压
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-0.5 line-clamp-1 text-[11px] text-[var(--text-secondary)]">
                        {item.section_title || item.title}
                      </p>
                      <p className="mt-0.5 text-[10px] text-[var(--text-secondary)]">
                        {item.learning_status === 'completed'
                          ? '已完成'
                          : item.is_active
                            ? '进行中 · 未完成'
                            : '未完成'}
                        {' · '}
                        {item.generated_by === 'llm' ? 'AI 讲义' : '模板讲义'}
                        {(item.units_packed || 1) > 1 ? ` · ${item.units_packed} 节` : ''}
                      </p>
                    </button>
                  </li>
                );
              })}
            </ul>
          </aside>

          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            {error && (
              <p className="mx-4 mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-[12px] text-red-600 sm:mx-5">
                {error}
              </p>
            )}
            {docLoading && (
              <div className="flex flex-col items-center justify-center gap-2 px-4 py-16 text-sm text-[var(--text-secondary)]">
                <Loader2 className="h-4 w-4 animate-spin" />
                {generating ? '正在生成讲义，可能需要一分钟…' : '正在加载讲义…'}
              </div>
            )}
            {!docLoading && selected && doc && (
              <>
                <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--border-color)] px-4 py-3 sm:px-5">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-[var(--text-primary)]">
                      {doc.doc_title} · {doc.section_title}
                    </p>
                    <p className="text-[11px] text-[var(--text-secondary)]">
                      {selected.date}
                      <span className="ml-2 rounded-md bg-amber-500/10 px-1.5 py-0.5 text-amber-800 dark:text-amber-200">
                        {doc.generated_by === 'llm' ? 'AI 讲义' : '模板讲义'}
                      </span>
                      <span
                        className={`ml-2 rounded-md px-1.5 py-0.5 ${
                          selected.learning_status === 'completed'
                            ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                            : 'bg-amber-500/10 text-amber-800 dark:text-amber-200'
                        }`}
                      >
                        {selected.learning_status === 'completed' ? '已完成' : '未完成'}
                      </span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={statusBusy}
                      onClick={() => {
                        if (!selectedDate) return;
                        void (async () => {
                          setStatusBusy(true);
                          try {
                            const next =
                              selected.learning_status === 'completed' ? 'pending' : 'completed';
                            await setInterviewLearningDayStatus(selectedDate, next);
                            await loadList();
                          } catch (err) {
                            setError(err instanceof Error ? err.message : '更新状态失败');
                          } finally {
                            setStatusBusy(false);
                          }
                        })();
                      }}
                      className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-[11px] disabled:opacity-50 ${
                        selected.learning_status === 'completed'
                          ? 'border-[var(--border-color)] text-[var(--text-secondary)]'
                          : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200'
                      }`}
                    >
                      {statusBusy ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <CheckCircle2 className="h-3 w-3" />
                      )}
                      {selected.learning_status === 'completed' ? '标为未完成' : '标为已完成'}
                    </button>
                    <button
                      type="button"
                      disabled={docLoading}
                      onClick={() =>
                        selectedDate && void loadDoc(selectedDate, { refresh: true, isGenerate: true })
                      }
                      className="rounded-lg border border-[var(--border-color)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:opacity-50"
                    >
                      重新生成
                    </button>
                  </div>
                </div>
                <LearningDocWorkspace
                  doc={doc}
                  docDate={selected.date}
                  onPractice={
                    onPractice
                      ? (topic) => {
                          onOpenChange(false);
                          onPractice(topic);
                        }
                      : undefined
                  }
                />
              </>
            )}
            {!docLoading && selected && !doc && !error && (
              <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
                {selected.has_doc ? (
                  <p className="text-sm text-[var(--text-secondary)]">选择日期查看讲义</p>
                ) : (
                  <>
                    <p className="text-sm text-[var(--text-secondary)]">
                      {selected.date} 还没有生成讲义
                    </p>
                    <p className="max-w-xs text-[12px] text-[var(--text-secondary)]">
                      生成可能需要约一分钟，完成后可随时回来查看。
                    </p>
                    <button
                      type="button"
                      onClick={() =>
                        selectedDate && void loadDoc(selectedDate, { isGenerate: true })
                      }
                      className="inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-amber-700"
                    >
                      <BookOpen className="h-4 w-4" />
                      生成讲义
                    </button>
                  </>
                )}
              </div>
            )}
            {!docLoading && !selected && !error && !listLoading && (
              <p className="py-12 text-center text-sm text-[var(--text-secondary)]">选择日期查看讲义</p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

