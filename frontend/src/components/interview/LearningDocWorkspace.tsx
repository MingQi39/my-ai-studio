import type { Components } from 'react-markdown';
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
} from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ExternalLink, Loader2, MessageSquareQuote, Send, X } from 'lucide-react';
import { useIsMobile } from '@/components/ui/use-mobile';
import { cn } from '@/components/ui/utils';
import { askInterviewLearningDoc, type TodayLearningDoc } from '@/services/api';

const QUICK_ASKS = [
  '这段是什么意思？',
  '面试里怎么口述？',
  '和相邻概念有什么区别？',
  '举一个工程落地例子',
] as const;

type QuotePickCtxValue = {
  active: boolean;
  onPick: (text: string) => void;
};

const QuotePickCtx = createContext<QuotePickCtxValue>({
  active: false,
  onPick: () => {},
});

function pickFromEvent(e: MouseEvent<HTMLElement> | KeyboardEvent<HTMLElement>) {
  return (e.currentTarget.innerText || '').replace(/\u00a0/g, ' ').trim();
}

function PickableBlock({
  as: Tag,
  className,
  children,
}: {
  as: 'p' | 'li' | 'blockquote' | 'h2' | 'h3' | 'h4';
  className: string;
  children: ReactNode;
}) {
  const { active, onPick } = useContext(QuotePickCtx);
  if (!active) {
    return <Tag className={className}>{children}</Tag>;
  }
  return (
    <Tag
      className={cn(
        className,
        'cursor-pointer rounded-lg ring-1 ring-amber-500/30 transition active:bg-amber-500/15',
      )}
      role="button"
      tabIndex={0}
      onClick={(e) => {
        e.preventDefault();
        const text = pickFromEvent(e);
        if (text.length >= 2) onPick(text);
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          const text = pickFromEvent(e);
          if (text.length >= 2) onPick(text);
        }
      }}
    >
      {children}
    </Tag>
  );
}

export const learningDocMarkdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mb-3 mt-6 break-words border-b border-[var(--border-color)] pb-2 text-xl font-bold tracking-tight text-[var(--text-primary)] first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <PickableBlock
      as="h2"
      className="mb-3 mt-7 break-words border-b border-amber-500/20 pb-1.5 text-lg font-semibold text-[var(--text-primary)] first:mt-0"
    >
      {children}
    </PickableBlock>
  ),
  h3: ({ children }) => (
    <PickableBlock
      as="h3"
      className="mb-2 mt-5 break-words text-base font-semibold text-[var(--text-primary)]"
    >
      {children}
    </PickableBlock>
  ),
  h4: ({ children }) => (
    <PickableBlock
      as="h4"
      className="mb-1.5 mt-4 break-words text-sm font-semibold text-[var(--text-primary)]"
    >
      {children}
    </PickableBlock>
  ),
  p: ({ children }) => (
    <PickableBlock as="p" className="my-2.5 break-words text-[13.5px] leading-7 text-[var(--text-primary)]">
      {children}
    </PickableBlock>
  ),
  ul: ({ children }) => (
    <ul className="my-3 list-disc space-y-1.5 break-words pl-5 text-[13.5px] leading-7 text-[var(--text-primary)]">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="my-3 list-decimal space-y-1.5 break-words pl-5 text-[13.5px] leading-7 text-[var(--text-primary)]">
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <PickableBlock as="li" className="break-words pl-0.5 marker:text-amber-600/80">
      {children}
    </PickableBlock>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-[var(--text-primary)]">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-[var(--text-secondary)]">{children}</em>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="break-words font-medium text-amber-700 underline decoration-amber-500/40 underline-offset-2 hover:text-amber-800 dark:text-amber-300"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <PickableBlock
      as="blockquote"
      className="my-4 break-words rounded-r-lg border-l-4 border-amber-500/50 bg-amber-500/5 py-2 pl-4 pr-3 text-[13px] leading-relaxed text-[var(--text-secondary)]"
    >
      {children}
    </PickableBlock>
  ),
  hr: () => <hr className="my-6 border-[var(--border-color)]" />,
  code: ({ className, children }) => {
    const isBlock = Boolean(className?.includes('language-'));
    if (isBlock) {
      return (
        <code className="block max-w-full overflow-x-auto whitespace-pre rounded-lg bg-[var(--bg-hover)] p-3 font-mono text-[12.5px] leading-6 text-[var(--text-primary)]">
          {children}
        </code>
      );
    }
    return (
      <code className="break-all rounded bg-[var(--bg-hover)] px-1.5 py-0.5 font-mono text-[12.5px] text-[var(--text-primary)]">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-4 max-w-full overflow-x-auto rounded-xl border border-[var(--border-color)] bg-[var(--bg-hover)] p-0">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-4 max-w-full overflow-x-auto rounded-xl border border-[var(--border-color)]">
      <table className="min-w-full border-collapse text-left text-[13px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-[var(--bg-hover)]">{children}</thead>,
  th: ({ children }) => (
    <th className="border-b border-[var(--border-color)] px-3 py-2 font-semibold text-[var(--text-primary)]">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="break-words border-b border-[var(--border-color)] px-3 py-2 text-[var(--text-primary)]">
      {children}
    </td>
  ),
};

function LearningAskPanel({
  doc,
  docDate,
  quote,
  onClearQuote,
  onRepick,
  mobileFull,
}: {
  doc: TodayLearningDoc;
  docDate?: string | null;
  quote: string;
  onClearQuote: () => void;
  onRepick?: () => void;
  mobileFull?: boolean;
}) {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (quote) inputRef.current?.focus();
  }, [quote]);

  const submit = async (q?: string) => {
    const nextQ = (q ?? question).trim();
    if (!quote.trim()) {
      setError(onRepick ? '请先点选一段讲义文字' : '请先在讲义中选中一段文字');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await askInterviewLearningDoc({
        quote,
        question: nextQ,
        topic: doc.topic,
        section_title: doc.section_title,
        doc_date: docDate,
      });
      setAnswer(result.answer);
      if (nextQ) setQuestion(nextQ);
    } catch (err) {
      setError(err instanceof Error ? err.message : '提问失败');
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className={cn('flex min-h-0 w-full flex-col bg-[var(--bg-main)]', mobileFull ? 'h-full flex-1' : 'h-full')}>
      <div className="shrink-0 border-b border-[var(--border-color)] px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
            <MessageSquareQuote className="h-4 w-4 text-amber-600" />
            引用提问
          </div>
          <button
            type="button"
            onClick={onClearQuote}
            className="rounded-md p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            aria-label="关闭提问面板"
            title="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-[var(--text-secondary)]">
          基于选中原文追问概念、口述与落地例子。
        </p>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto overflow-x-hidden px-4 py-3">
        {quote ? (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2">
            <div className="flex items-start justify-between gap-2">
              <p className="text-[10px] font-medium uppercase tracking-wide text-amber-700 dark:text-amber-300">
                引用
              </p>
              <div className="flex items-center gap-2">
                {onRepick && (
                  <button
                    type="button"
                    onClick={onRepick}
                    className="text-[11px] text-amber-800 hover:underline dark:text-amber-200"
                  >
                    重选
                  </button>
                )}
                <button
                  type="button"
                  onClick={onClearQuote}
                  className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  aria-label="关闭提问面板"
                  title="关闭"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            <p className="mt-1 max-h-28 overflow-y-auto break-words text-[12px] leading-relaxed text-[var(--text-primary)]">
              {quote}
            </p>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-1.5">
          {QUICK_ASKS.map((item) => (
            <button
              key={item}
              type="button"
              disabled={busy || !quote}
              onClick={() => void submit(item)}
              className="rounded-full border border-[var(--border-color)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)] hover:border-amber-500/40 hover:bg-amber-500/10 hover:text-amber-900 disabled:opacity-40 dark:hover:text-amber-100"
            >
              {item}
            </button>
          ))}
        </div>

        {error && (
          <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-[12px] text-red-600">
            {error}
          </p>
        )}

        {busy && (
          <div className="flex items-center gap-2 text-[12px] text-[var(--text-secondary)]">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            AI 正在根据引用作答…
          </div>
        )}

        {answer && !busy && (
          <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-hover)]/40 px-3 py-2.5">
            <p className="mb-2 text-[10px] font-medium text-[var(--text-secondary)]">AI 回答</p>
            <div className="learning-doc-md min-w-0 max-w-full break-words [&_h2]:mt-3 [&_h2]:text-sm [&_p]:my-1.5 [&_p]:text-[12.5px] [&_p]:leading-6">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={learningDocMarkdownComponents}>
                {answer}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-[var(--border-color)] p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={2}
            placeholder={quote ? '针对引用继续追问…' : '先选一段讲义文字'}
            disabled={busy}
            className="min-h-[2.75rem] min-w-0 flex-1 resize-none rounded-xl border border-[var(--border-color)] bg-transparent px-3 py-2 text-[12.5px] text-[var(--text-primary)] outline-none focus:border-amber-500/50"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void submit();
              }
            }}
          />
          <button
            type="button"
            disabled={busy || !quote.trim()}
            onClick={() => void submit()}
            className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-40"
            aria-label="发送提问"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </aside>
  );
}

export function LearningDocWorkspace({
  doc,
  docDate,
  onPractice,
  showGoalBanner = true,
  statusControls,
  banner,
  enableAsk = true,
}: {
  doc: TodayLearningDoc;
  docDate?: string | null;
  onPractice?: (topic: string) => void;
  showGoalBanner?: boolean;
  statusControls?: ReactNode;
  banner?: ReactNode;
  enableAsk?: boolean;
}) {
  const isMobile = useIsMobile();
  const markdownHasGoal = Boolean(doc.markdown_body?.includes('## 今日目标'));
  const articleRef = useRef<HTMLDivElement>(null);
  const [quote, setQuote] = useState('');
  const [askOpen, setAskOpen] = useState(false);
  const [pickMode, setPickMode] = useState(false);
  const [toolbar, setToolbar] = useState<{ top: number; left: number; text: string } | null>(null);

  useEffect(() => {
    // 手机端用点选，不走划词浮层
    if (!enableAsk || isMobile) {
      setToolbar(null);
      return;
    }

    const syncToolbar = () => {
      const sel = window.getSelection();
      const text = sel?.toString().trim() || '';
      if (!text || text.length < 2) {
        setToolbar(null);
        return;
      }
      const anchor = sel?.anchorNode;
      if (!anchor || !articleRef.current?.contains(anchor)) {
        setToolbar(null);
        return;
      }
      const range = sel!.rangeCount ? sel!.getRangeAt(0) : null;
      if (!range) {
        setToolbar(null);
        return;
      }
      const rect = range.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) {
        setToolbar(null);
        return;
      }
      const host = articleRef.current.getBoundingClientRect();
      setToolbar({
        text,
        top: Math.max(8, rect.top - host.top - 40),
        left: Math.min(
          Math.max(8, rect.left - host.left + rect.width / 2 - 56),
          Math.max(8, host.width - 120),
        ),
      });
    };

    document.addEventListener('mouseup', syncToolbar);
    return () => document.removeEventListener('mouseup', syncToolbar);
  }, [enableAsk, isMobile]);

  const closeAsk = () => {
    setAskOpen(false);
    setQuote('');
    setPickMode(false);
  };

  const openPickMode = () => {
    setAskOpen(false);
    setToolbar(null);
    setPickMode(true);
  };

  const onPickQuote = (text: string) => {
    setQuote(text);
    setPickMode(false);
    setAskOpen(true);
    setToolbar(null);
    window.getSelection()?.removeAllRanges();
  };

  const articleBody = (
    <>
      {banner}
      {statusControls}
      {showGoalBanner && doc.today_goal && !markdownHasGoal && (
        <p className="mb-4 break-words rounded-xl bg-amber-500/10 px-3.5 py-2.5 text-[12.5px] leading-relaxed text-amber-900 dark:text-amber-100">
          {doc.today_goal}
        </p>
      )}
      {pickMode && (
        <div className="sticky top-0 z-10 mb-3 flex items-center justify-between gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-900 dark:text-amber-100">
          <span>点选下面任意一段作为引用</span>
          <button
            type="button"
            onClick={() => setPickMode(false)}
            className="shrink-0 rounded-md px-2 py-1 text-[11px] hover:bg-amber-500/20"
          >
            取消
          </button>
        </div>
      )}
      {!isMobile && toolbar && (
        <button
          type="button"
          className="absolute z-20 inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-[var(--bg-main)] px-3 py-1.5 text-[11px] font-medium text-amber-900 shadow-md hover:bg-amber-500/10 dark:text-amber-100"
          style={{ top: toolbar.top, left: toolbar.left }}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            setQuote(toolbar.text);
            setAskOpen(true);
            setToolbar(null);
            window.getSelection()?.removeAllRanges();
          }}
        >
          <MessageSquareQuote className="h-3.5 w-3.5" />
          引用提问
        </button>
      )}
      <QuotePickCtx.Provider value={{ active: pickMode, onPick: onPickQuote }}>
        {doc.markdown_body ? (
          <div className="learning-doc-md min-w-0 max-w-full break-words selection:bg-amber-500/25">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={learningDocMarkdownComponents}>
              {doc.markdown_body}
            </ReactMarkdown>
          </div>
        ) : (
          <ul className="mt-1 space-y-2">
            {doc.reading_bullets.map((bullet) => (
              <li key={bullet}>
                {pickMode ? (
                  <button
                    type="button"
                    onClick={() => onPickQuote(bullet)}
                    className="w-full rounded-lg px-1 py-1 text-left text-[13px] leading-relaxed text-[var(--text-secondary)] ring-1 ring-amber-500/30 active:bg-amber-500/15"
                  >
                    · {bullet}
                  </button>
                ) : (
                  <span className="break-words text-[13px] leading-relaxed text-[var(--text-secondary)]">
                    · {bullet}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </QuotePickCtx.Provider>
      {!doc.markdown_body && doc.bank_excerpts.length > 0 && (
        <div className="mt-5 border-t border-[var(--border-color)] pt-4">
          <p className="text-[11px] font-medium text-[var(--text-secondary)]">题库延伸</p>
          <ul className="mt-2 space-y-1.5">
            {doc.bank_excerpts.map((q) => (
              <li key={q} className="break-words text-[12px] leading-snug text-[var(--text-primary)]">
                {q}
              </li>
            ))}
          </ul>
        </div>
      )}
      {doc.source_links && doc.source_links.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2 border-t border-[var(--border-color)] pt-4">
          {doc.source_links.map((link) => (
            <a
              key={link.url}
              href={link.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex max-w-full items-center gap-1 rounded-lg border border-[var(--border-color)] px-2.5 py-1 text-[11px] text-amber-800 hover:bg-amber-500/10 dark:text-amber-200"
            >
              <span className="truncate">{link.title}</span>
              <ExternalLink className="h-3 w-3 shrink-0" />
            </a>
          ))}
        </div>
      )}
      {doc.comic_url && (
        <img
          src={doc.comic_url}
          alt={`${doc.topic} 概念图`}
          className="mt-4 max-h-48 w-full max-w-full rounded-xl border border-[var(--border-color)] object-cover object-top"
        />
      )}
      {onPractice && (
        <button
          type="button"
          onClick={() => onPractice(doc.topic)}
          className="mt-5 w-full rounded-xl bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-amber-700"
        >
          {doc.practice_task || `学完去练 · ${doc.topic}`}
        </button>
      )}
    </>
  );

  const articleShell = (
    <div className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div
        className="relative min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-4 sm:px-6"
        ref={articleRef}
      >
        {articleBody}
      </div>
      {enableAsk && isMobile && !askOpen && !pickMode && (
        <div className="shrink-0 border-t border-[var(--border-color)] bg-[var(--bg-main)] p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          <button
            type="button"
            onClick={openPickMode}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-sm font-medium text-amber-900 dark:text-amber-100"
          >
            <MessageSquareQuote className="h-4 w-4" />
            点选一段提问
          </button>
        </div>
      )}
    </div>
  );

  if (!enableAsk) return articleShell;

  // 手机：提问时全屏提问面板，避免和讲义抢高度
  if (isMobile && askOpen) {
    return (
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <LearningAskPanel
          doc={doc}
          docDate={docDate}
          quote={quote}
          onClearQuote={closeAsk}
          onRepick={openPickMode}
          mobileFull
        />
      </div>
    );
  }

  if (!askOpen) return articleShell;

  // 桌面：左右分栏
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden md:flex-row">
      {articleShell}
      <div className="flex min-h-0 w-full min-w-0 shrink-0 flex-col border-t border-[var(--border-color)] md:w-[320px] md:border-l md:border-t-0 lg:w-[360px]">
        <LearningAskPanel doc={doc} docDate={docDate} quote={quote} onClearQuote={closeAsk} />
      </div>
    </div>
  );
}
