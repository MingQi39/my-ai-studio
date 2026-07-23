import { useEffect, useRef, useState, type Dispatch, type ReactNode, type SetStateAction } from 'react';
import { useTranslation } from 'react-i18next';
import {
  HistoryLearningDialog,
  HistoryLearningEntryCard,
  HistoryLearningHeaderButton,
  TodayLearningCompactCard,
  TodayLearningDialog,
  TodayLearningHeaderButton,
} from '@/components/interview/TodayLearningPanel';
import { InterviewSettingsSheet } from '@/components/interview/InterviewSettingsSheet';
import {
  attemptCtaKind,
  goalCoreChanged,
  type GoalCore,
} from '@/components/interview/interviewGoalDraft';
import { VoiceAnswerControls } from '@/components/interview/VoiceAnswerControls';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  ArrowRight,
  Bell,
  BookOpen,
  Check,
  FileUp,
  Lightbulb,
  Loader2,
  Map,
  Menu,
  PanelLeft,
  PanelRight,
  SkipForward,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/components/ui/utils';
import {
  abandonInterviewAttempt,
  ApiError,
  commitInterviewAttempt,
  confirmInterviewClaim,
  craftInterviewResume,
  createInterviewAttempt,
  extractResume,
  getActiveInterviewAttempt,
  getInterviewAttemptHint,
  getInterviewProfile,
  getInterviewPushSettings,
  getInterviewTodayPlan,
  getInterviewTrainingProgress,
  getResumeEligibility,
  listInterviewClaims,
  listReviewCards,
  saveInterviewClaim,
  submitInterviewAttemptAnswer,
  updateInterviewProfile,
  updateInterviewPushSettings,
  type InterviewAttempt,
  type InterviewFeedback,
  type InterviewPushSettings,
  type InterviewReviewCard,
  type InterviewTodayPlan,
  type InterviewTrainingProgress,
  type PushFrequency,
  type ResumeCandidate,
  type ResumeEligibility,
} from '@/services/api';
import { PUSH_FREQUENCY_OPTIONS, pushInterviewNow, requestInterviewPushPermission, useInterviewPush } from '@/hooks/useInterviewPush';
import { getPlatform } from '@/platform';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

type Phase = 'loading' | 'setup' | 'import' | 'confirm' | 'train';
type Level = 'P5' | 'P6' | 'P7';
type Difficulty = '初级' | '中级' | '高级';
type BusyKind = false | 'loading' | 'submitting' | 'hinting' | 'committing';

const ROLE_OPTIONS = ['前端', '全栈', '后端', 'AI 应用工程'] as const;
const DIFFICULTY_OPTIONS: { label: Difficulty; level: Level; desc: string }[] = [
  { label: '初级', level: 'P5', desc: '定位与基础表达' },
  { label: '中级', level: 'P6', desc: '机制与取舍' },
  { label: '高级', level: 'P7', desc: '工程证据与风险' },
];
const SALARY_OPTIONS = ['15-25k', '25-40k', '40-60k', '60k+'] as const;
const CATEGORY_LABEL: Record<ResumeCandidate['category'], string> = {
  skill: '技术',
  project: '项目经历',
  role: '工作经历',
};

function difficultyToLevel(difficulty: Difficulty): Level {
  return DIFFICULTY_OPTIONS.find((d) => d.label === difficulty)?.level ?? 'P6';
}

function levelToDifficulty(level: string | null | undefined): Difficulty {
  if (level === '初级' || level === 'P5') return '初级';
  if (level === '高级' || level === 'P7') return '高级';
  if (level === '中级' || level === 'P6') return '中级';
  return '中级';
}

/** 答题路径节点：后端仍用英文 ID，界面显示简洁中文 */
const ROUTE_NODE_LABELS: Record<string, string> = {
  Position: '解决什么问题',
  Principle: '底层原理',
  Mechanism: '怎么实现',
  'Trade-off': '方案取舍',
  Evidence: '项目证据',
};

function routeNodeLabel(node: string): string {
  return ROUTE_NODE_LABELS[node] ?? node;
}

const TIER_LABEL: Record<InterviewTrainingProgress['goal']['tier'], string> = {
  low: '入门',
  mid: '中级',
  high: '高薪',
};

function MetricBar({ value, max = 1 }: { value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, max > 0 ? (value / max) * 100 : 0));
  return (
    <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[var(--border-color)]/60">
      <div className="h-full rounded-full bg-amber-500/80 transition-[width] duration-300" style={{ width: `${pct}%` }} />
    </div>
  );
}

function useMinWidth(minWidth: number) {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth >= minWidth : true,
  );

  useEffect(() => {
    const mql = window.matchMedia(`(min-width: ${minWidth}px)`);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [minWidth]);

  return matches;
}

/** narrow <1280 drawer · medium 1280–1535 compact 3-col · wide ≥1536 full rails */
type TrainLayoutTier = 'narrow' | 'medium' | 'wide';

function useTrainLayoutTier(): TrainLayoutTier {
  const isWide = useMinWidth(1536);
  const isMedium = useMinWidth(1280);
  if (isWide) return 'wide';
  if (isMedium) return 'medium';
  return 'narrow';
}

function SidebarToggle({
  isSidebarOpen,
  toggleSidebar,
}: {
  isSidebarOpen: boolean;
  toggleSidebar?: () => void;
}) {
  const { t } = useTranslation();
  if (!toggleSidebar) return null;
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggleSidebar}
      aria-label={isSidebarOpen ? t('sidebar.collapse') : t('sidebar.expand')}
      title={isSidebarOpen ? t('sidebar.collapse') : t('sidebar.expand')}
      className={cn(
        'h-9 w-9 shrink-0 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]',
        isSidebarOpen ? 'md:hidden' : '',
      )}
    >
      <Menu size={20} />
    </Button>
  );
}

function TrainSideRail({
  open,
  onClose,
  side,
  isWide,
  widthClass,
  title,
  presentation = 'side',
  children,
}: {
  open: boolean;
  onClose: () => void;
  side: 'left' | 'right';
  isWide: boolean;
  widthClass: string;
  title?: string;
  /** narrow 下 left 用 bottom，避免窄侧栏里叠两块长内容 */
  presentation?: 'side' | 'bottom';
  children: ReactNode;
}) {
  if (isWide) {
    return (
      <div
        className={cn(
          'h-full flex-shrink-0 overflow-hidden transition-[width,opacity] duration-300 ease-in-out',
          open ? cn(widthClass, 'opacity-100') : 'w-0 opacity-0',
        )}
      >
        <div className={cn('flex h-full flex-col gap-4 overflow-y-auto', widthClass)}>{children}</div>
      </div>
    );
  }

  const isBottom = presentation === 'bottom';

  return (
    <div
      className={cn(
        'fixed inset-0 z-30',
        open ? 'pointer-events-auto' : 'pointer-events-none',
      )}
      aria-hidden={!open}
    >
      <button
        type="button"
        className={cn(
          'absolute inset-0 bg-black/40 transition-opacity duration-300',
          open ? 'opacity-100' : 'opacity-0',
        )}
        onClick={onClose}
        aria-label={side === 'left' ? '关闭训练导航' : '关闭反馈面板'}
      />
      <div
        className={cn(
          'absolute flex flex-col bg-[var(--bg-main)] shadow-2xl transition-transform duration-300 ease-in-out',
          isBottom
            ? cn(
                'inset-x-0 bottom-0 max-h-[min(88dvh,88vh)] rounded-t-2xl border-t border-[var(--border-color)]',
                open ? 'translate-y-0' : 'translate-y-full',
              )
            : cn(
                'inset-y-0 w-[min(320px,92vw)]',
                side === 'left' ? 'left-0' : 'right-0',
                open
                  ? 'translate-x-0'
                  : side === 'left'
                    ? '-translate-x-full'
                    : 'translate-x-full',
              ),
        )}
      >
        <div
          className={cn(
            'flex shrink-0 items-center gap-2 border-b border-[var(--border-color)] px-3',
            isBottom ? 'pt-2 pb-2.5' : 'py-2.5',
          )}
        >
          {isBottom && (
            <div className="absolute left-1/2 top-1.5 h-1 w-10 -translate-x-1/2 rounded-full bg-[var(--border-color)]" />
          )}
          <p
            className={cn(
              'min-w-0 flex-1 truncate text-sm font-semibold text-[var(--text-primary)]',
              isBottom && 'pt-2',
            )}
          >
            {title || (side === 'left' ? '训练导航' : '反馈')}
          </p>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div
          className={cn(
            'min-h-0 flex-1 space-y-3 overflow-y-auto overflow-x-hidden p-3',
            'pb-[max(0.75rem,env(safe-area-inset-bottom))]',
          )}
        >
          {children}
        </div>
      </div>
    </div>
  );
}

function ProgressPanel({
  progress,
  todayPlan,
  todayPlanLoading,
  onOpenTodayLearning,
  onOpenHistoryLearning,
  onStartModule,
  onProjectSim,
  dense = false,
}: {
  progress: InterviewTrainingProgress;
  todayPlan?: InterviewTodayPlan | null;
  todayPlanLoading?: boolean;
  onOpenTodayLearning?: () => void;
  onOpenHistoryLearning?: () => void;
  onStartModule?: (topic: string) => void;
  onProjectSim?: () => void;
  /** Medium layout: drop header-duplicated cards and tighten spacing */
  dense?: boolean;
}) {
  const [openDetail, setOpenDetail] = useState(false);
  const { coverage, route_depth: depth, retention, expectations, next_step, composite, weekly_trend, learning_path } =
    progress;
  const maxCommit = Math.max(1, ...weekly_trend.map((w) => w.committed_count));
  const metCount = expectations.filter((e) => e.met).length;
  const hasTrend = weekly_trend.some((w) => w.committed_count > 0);
  const nextMod = learning_path?.next_module;

  return (
    <div className={dense ? 'space-y-3' : 'space-y-5'}>
      {!dense && (
        <>
          <TodayLearningCompactCard
            todayPlan={todayPlan ?? null}
            loading={todayPlanLoading}
            onOpenFull={onOpenTodayLearning}
          />
          {onOpenHistoryLearning && <HistoryLearningEntryCard onOpen={onOpenHistoryLearning} />}
        </>
      )}

      {todayPlan && !todayPlan.learning_doc && (todayPlan.tasks.length > 0 || todayPlan.due_review_count > 0) && (
        <div className={cn('rounded-xl border border-amber-500/30 bg-amber-500/5', dense ? 'p-2.5' : 'p-3')}>
          <p className="text-[10px] font-medium tracking-wide text-amber-700 dark:text-amber-300">
            今日计划 · {todayPlan.date}
          </p>
          {todayPlan.tasks.map((task) => (
            <div key={`${task.date}-${task.topic}-${task.task_type}`} className="mt-2">
              <p className="text-sm font-medium text-[var(--text-primary)]">
                {task.task_type === 'review' ? '复习' : task.task_type === 'consolidate' ? '巩固' : '训练'} ·{' '}
                {task.title}
              </p>
              <p className="mt-1 text-[11px] leading-relaxed text-[var(--text-secondary)]">{task.message}</p>
              {onStartModule && task.task_type !== 'review' && (
                <button
                  type="button"
                  onClick={() => onStartModule(task.topic)}
                  className="mt-2 rounded-lg bg-amber-500/15 px-2.5 py-1.5 text-[11px] font-semibold text-amber-800 dark:text-amber-200"
                >
                  开始练 {task.topic}
                </button>
              )}
            </div>
          ))}
          {todayPlan.due_review_count > 0 && (
            <p className="mt-2 text-[11px] text-[var(--text-secondary)]">
              另有 {todayPlan.due_review_count} 张复习卡到期
            </p>
          )}
        </div>
      )}

      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-medium tracking-wide text-[var(--text-secondary)]">
            综合进展 · {TIER_LABEL[progress.goal.tier]}对齐
          </p>
          <p
            className={cn(
              'mt-1 font-semibold tabular-nums leading-none text-[var(--text-primary)]',
              dense ? 'text-2xl' : 'text-3xl',
            )}
          >
            {composite.score}
            <span className="ml-1 text-sm font-normal text-[var(--text-secondary)]">/100</span>
          </p>
        </div>
        {!dense && (
          <p className="max-w-[9rem] text-right text-[10px] leading-snug text-[var(--text-secondary)]">
            仅计完成闭环与复习
          </p>
        )}
      </div>

      {nextMod && (
        <div className={cn('rounded-xl border border-[var(--border-color)] bg-[var(--bg-main)]', dense ? 'p-2.5' : 'p-3')}>
          <p className="text-[10px] font-medium tracking-wide text-[var(--text-secondary)]">
            学习路线 · {learning_path?.done_count ?? 0}/{learning_path?.total_relevant ?? 0} 阶段
          </p>
          <p className="mt-1 text-sm font-medium text-[var(--text-primary)]">下一模块：{nextMod.title}</p>
          {!dense && (
            <p className="mt-1 text-[11px] leading-relaxed text-[var(--text-secondary)]">{nextMod.reason}</p>
          )}
          <div className="mt-2.5 flex flex-wrap gap-2">
            {onStartModule && (
              <button
                type="button"
                onClick={() => onStartModule(nextMod.topic)}
                className="rounded-lg bg-amber-500/15 px-2.5 py-1.5 text-[11px] font-semibold text-amber-800 dark:text-amber-200"
              >
                练 {nextMod.topic}
              </button>
            )}
            {onProjectSim && (
              <button
                type="button"
                onClick={onProjectSim}
                className="rounded-lg border border-[var(--border-color)] px-2.5 py-1.5 text-[11px] text-[var(--text-primary)]"
              >
                项目模拟
              </button>
            )}
          </div>
        </div>
      )}

      <div className={dense ? 'space-y-2.5' : 'space-y-4'}>
        <div>
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs text-[var(--text-primary)]">主题覆盖</span>
            <span className="text-xs tabular-nums text-[var(--text-secondary)]">
              {coverage.covered_count}/{coverage.total_count}
            </span>
          </div>
          <MetricBar value={coverage.covered_count} max={Math.max(1, coverage.total_count)} />
        </div>
        <div>
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs text-[var(--text-primary)]">闭环深度</span>
            <span className="text-xs tabular-nums text-[var(--text-secondary)]">
              近{depth.window_days}天 {depth.committed_count} 次
            </span>
          </div>
          <MetricBar
            value={depth.tradeoff_rate * 0.6 + depth.evidence_rate * 0.4}
            max={1}
          />
          {!dense && (
            <p className="mt-1 text-[10px] text-[var(--text-secondary)]">
              取舍 {Math.round(depth.tradeoff_rate * 100)}% · 证据 {Math.round(depth.evidence_rate * 100)}%
            </p>
          )}
        </div>
        <div>
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs text-[var(--text-primary)]">复习健康</span>
            <span className="text-xs tabular-nums text-[var(--text-secondary)]">
              到期 {retention.due_count} · 巩固 {retention.consolidated_count}
            </span>
          </div>
          <MetricBar value={retention.healthy_ratio} max={1} />
        </div>
      </div>

      <p
        className={cn(
          'rounded-xl bg-amber-500/10 leading-relaxed text-amber-900 dark:text-amber-100',
          dense ? 'line-clamp-3 px-2.5 py-2 text-[11px]' : 'px-3 py-2.5 text-[12px]',
        )}
      >
        {next_step}
      </p>

      <button
        type="button"
        onClick={() => setOpenDetail((v) => !v)}
        className="flex w-full items-center justify-between rounded-lg py-1 text-left text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      >
        <span>
          期望清单 {metCount}/{expectations.length}
          {hasTrend ? ' · 周趋势' : ''}
          {composite.cap_reason ? ' · 有封顶说明' : ''}
        </span>
        <span className="tabular-nums">{openDetail ? '收起' : '展开'}</span>
      </button>

      {openDetail && (
        <div className="space-y-4 border-t border-[var(--border-color)] pt-4">
          <ul className="space-y-2.5">
            {expectations.map((item) => (
              <li key={item.id} className="flex gap-2 text-[11px] leading-snug">
                <span className={`mt-0.5 ${item.met ? 'text-emerald-600' : 'text-[var(--text-secondary)]'}`}>
                  {item.met ? '✓' : '○'}
                </span>
                <span>
                  <span className="text-[var(--text-primary)]">{item.label}</span>
                  <span className="mt-0.5 block text-[var(--text-secondary)]">{item.detail}</span>
                </span>
              </li>
            ))}
          </ul>

          {hasTrend && (
            <div>
              <p className="mb-2 text-[11px] text-[var(--text-secondary)]">近几周闭环次数</p>
              <div className="flex h-12 items-end gap-1.5">
                {weekly_trend.map((w) => (
                  <div
                    key={w.week_start}
                    className="flex-1 rounded-sm bg-amber-500/55"
                    style={{
                      height: `${Math.max(6, (w.committed_count / maxCommit) * 100)}%`,
                    }}
                    title={`${w.week_start}: ${w.committed_count}`}
                  />
                ))}
              </div>
            </div>
          )}

          <p className="text-[10px] leading-relaxed text-[var(--text-secondary)]">
            {composite.formula}
            {composite.cap_reason ? ` · ${composite.cap_reason}` : ''}
          </p>
        </div>
      )}
    </div>
  );
}

function AtlasPath({ nodes, focus }: { nodes: string[]; focus?: string }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-1 gap-y-2 text-[13px]">
      {nodes.map((node, index) => {
        const active = focus
          ? node === focus || node.toLowerCase().includes(focus.toLowerCase())
          : index === Math.min(2, nodes.length - 1);
        return (
          <li key={`${node}-${index}`} className="flex items-center gap-1">
            {index > 0 && <span className="px-0.5 text-[var(--text-secondary)] opacity-40">→</span>}
            <span
              className={
                active
                  ? 'rounded-md bg-amber-500/15 px-2 py-0.5 font-semibold text-amber-700 dark:text-amber-300'
                  : 'rounded-md px-2 py-0.5 text-[var(--text-secondary)]'
              }
            >
              {routeNodeLabel(node)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function AtlasRailBody({
  training,
  topics,
  customTopic,
  setCustomTopic,
  setTopics,
  cards,
  hasResumeClaims,
  busy,
  comicCollapsed,
  onToggleComic,
  onOpenComic,
  onPickTopic,
  extrasOpen,
  onToggleExtras,
  compactExtras = false,
}: {
  training: Pick<
    InterviewAttempt,
    'topic' | 'atlas' | 'comic_url' | 'training_mode' | 'structure_hint'
  >;
  topics: string[];
  customTopic: string;
  setCustomTopic: (v: string) => void;
  setTopics: Dispatch<SetStateAction<string[]>>;
  cards: InterviewReviewCard[];
  hasResumeClaims: boolean;
  busy: BusyKind;
  comicCollapsed?: boolean;
  onToggleComic?: () => void;
  onOpenComic: (src: string, alt: string) => void;
  onPickTopic: (topic: string) => void;
  extrasOpen?: boolean;
  onToggleExtras?: () => void;
  compactExtras?: boolean;
}) {
  const comicBlock = training.comic_url ? (
    comicCollapsed ? (
      <button
        type="button"
        onClick={onToggleComic}
        className="mt-3 flex w-full items-center justify-between rounded-xl border border-[var(--border-color)] px-3 py-2.5 text-left text-[12px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
      >
        <span>模块入门漫画</span>
        <span className="text-amber-700 dark:text-amber-300">展开预览</span>
      </button>
    ) : (
      <div className="mt-3 space-y-2">
        {onToggleComic && (
          <button
            type="button"
            onClick={onToggleComic}
            className="text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            收起漫画
          </button>
        )}
        <button
          type="button"
          className="block w-full overflow-hidden rounded-xl border border-[var(--border-color)] text-left"
          onClick={() => onOpenComic(training.comic_url!, `${training.topic} 概念图`)}
          title="点击查看大图"
        >
          <img
            src={training.comic_url}
            alt={`${training.topic} 概念图`}
            className="max-h-36 w-full object-cover object-top"
          />
          <p className="px-2 py-1.5 text-[10px] text-[var(--text-secondary)]">模块入门漫画 · 点击放大</p>
        </button>
      </div>
    )
  ) : null;

  const topicPicker = (
    <>
      <p className="mb-2 text-xs font-medium text-[var(--text-secondary)]">
        {hasResumeClaims ? '目标题库 + 简历经历' : '按岗位生成的题库'}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {topics.slice(0, 12).map((topic) => (
          <button
            key={topic}
            type="button"
            onClick={() => onPickTopic(topic)}
            className={`min-h-9 rounded-lg px-2.5 py-1.5 text-xs ${
              training.topic === topic
                ? 'bg-amber-500/15 font-semibold text-amber-700 dark:text-amber-300'
                : 'bg-[var(--bg-main)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {topic}
          </button>
        ))}
      </div>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const topic = customTopic.trim();
          if (!topic) return;
          setTopics((prev) => (prev.includes(topic) ? prev : [topic, ...prev].slice(0, 12)));
          setCustomTopic('');
          onPickTopic(topic);
        }}
      >
        <input
          value={customTopic}
          onChange={(e) => setCustomTopic(e.target.value)}
          placeholder="自定义主题"
          className="min-h-9 min-w-0 flex-1 rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] px-2.5 py-1.5 text-xs text-[var(--text-primary)] outline-none focus:border-amber-500/50"
        />
        <button
          type="submit"
          disabled={!!busy || !customTopic.trim()}
          className="min-h-9 rounded-lg border border-[var(--border-color)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] disabled:opacity-50"
        >
          练这个
        </button>
      </form>
    </>
  );

  const reviewCards =
    cards.length > 0 ? (
      <ul className="space-y-2">
        {cards.slice(0, 5).map((card) => (
          <li key={card.id}>
            <button
              type="button"
              onClick={() => onPickTopic(card.topic)}
              className="w-full rounded-lg border border-[var(--border-color)] px-3 py-2.5 text-left text-xs hover:border-amber-500/40"
            >
              <span className="font-medium text-[var(--text-primary)]">{card.topic}</span>
              <span className="mt-1 block text-[var(--text-secondary)]">
                {card.next_due_at ? `到期 · ` : ''}
                卡在：
                {card.missing_nodes.slice(0, 2).map(routeNodeLabel).join('、') || '—'}
              </span>
            </button>
          </li>
        ))}
      </ul>
    ) : null;

  if (compactExtras) {
    return (
      <>
        <p className="mb-2 text-[10px] font-medium tracking-wide text-[var(--text-secondary)]">
          面试地图 · 当前路径
        </p>
        <AtlasPath nodes={training.atlas} focus={training.topic} />
        {training.training_mode === 'project_sim' && training.structure_hint && (
          <p className="mt-2 rounded-lg bg-sky-500/10 px-2.5 py-2 text-[11px] leading-relaxed text-sky-900 dark:text-sky-100">
            项目模拟 · {training.structure_hint}
          </p>
        )}
        <button
          type="button"
          onClick={onToggleExtras}
          className="mt-3 flex min-h-10 w-full items-center justify-between rounded-lg py-1 text-left text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <span>
            题库 / 漫画 / 复习
            {cards.length > 0 ? ` · ${Math.min(cards.length, 5)} 张卡` : ''}
          </span>
          <span>{extrasOpen ? '收起' : '展开'}</span>
        </button>
        {extrasOpen && (
          <div className="mt-2 space-y-3">
            {comicBlock}
            {topicPicker}
            {reviewCards}
          </div>
        )}
      </>
    );
  }

  return (
    <>
      <p className="mb-3 text-xs text-[var(--text-secondary)]">当前问题在路径中的位置</p>
      <AtlasPath nodes={training.atlas} focus={training.topic} />
      {comicBlock}
      {training.training_mode === 'project_sim' && training.structure_hint && (
        <p className="mt-3 rounded-lg bg-sky-500/10 px-2.5 py-2 text-[11px] leading-relaxed text-sky-900 dark:text-sky-100">
          项目模拟 · {training.structure_hint}
        </p>
      )}
      <div className="my-5 h-px bg-[var(--border-color)]" />
      {topicPicker}
      {cards.length > 0 && (
        <>
          <div className="my-5 h-px bg-[var(--border-color)]" />
          <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)]">
            <Map className="h-3.5 w-3.5" />
            待复习断点
          </p>
          {reviewCards}
        </>
      )}
    </>
  );
}

function RouteChecklist({
  nodes,
  covered,
  missing,
  focus,
}: {
  nodes: string[];
  covered: string[];
  missing: string[];
  focus?: string;
}) {
  return (
    <ul className="space-y-2">
      {nodes.map((node) => {
        const done = covered.includes(node);
        const gap = missing.includes(node);
        const isFocus = focus === node;
        return (
          <li
            key={node}
            className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm ${
              isFocus ? 'bg-amber-500/10 text-amber-800 dark:text-amber-200' : 'text-[var(--text-primary)]'
            }`}
          >
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                done
                  ? 'bg-emerald-600 text-white'
                  : gap
                    ? 'border border-dashed border-[var(--border-color)] text-[var(--text-secondary)]'
                    : 'border border-[var(--border-color)] text-[var(--text-secondary)]'
              }`}
            >
              {done ? '✓' : '○'}
            </span>
            <span>{routeNodeLabel(node)}</span>
            {isFocus && (
              <span className="ml-auto text-[11px] tracking-wide text-amber-600">当前重点</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Panel({
  title,
  eyebrow,
  children,
  className = '',
  compact = false,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  className?: string;
  /** Medium screens: tighter chrome so the practice column keeps room */
  compact?: boolean;
}) {
  return (
    <section
      className={`flex min-h-0 flex-col rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] ${className}`}
    >
      <header
        className={cn(
          'border-b border-[var(--border-color)]',
          compact ? 'px-3.5 py-3' : 'px-5 py-4',
        )}
      >
        {eyebrow && (
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-secondary)]">
            {eyebrow}
          </p>
        )}
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
      </header>
      <div className={cn('min-h-0 flex-1 overflow-y-auto', compact ? 'p-3.5' : 'p-5')}>{children}</div>
    </section>
  );
}

function ChoiceGroup({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <p className="text-sm font-medium text-[var(--text-primary)]">{label}</p>
      <div className="mt-3 flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function ChoiceButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-sm transition ${
        active
          ? 'bg-[var(--text-primary)] text-[var(--bg-card)]'
          : 'border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
      }`}
    >
      {children}
    </button>
  );
}

interface InterviewPageProps {
  isSidebarOpen?: boolean;
  toggleSidebar?: () => void;
}

export function InterviewPage({
  isSidebarOpen = true,
  toggleSidebar,
}: InterviewPageProps) {
  const { t } = useTranslation();
  const platform = getPlatform();
  const fileRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>('loading');
  const [busy, setBusy] = useState<BusyKind>(false);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<ResumeCandidate[]>([]);
  const [targetRole, setTargetRole] = useState('全栈');
  const [customRole, setCustomRole] = useState('');
  const [difficulty, setDifficulty] = useState<Difficulty>('中级');
  const [salaryBand, setSalaryBand] = useState<string>('25-40k');
  const [level, setLevel] = useState<Level>('P6');
  const [attempt, setAttempt] = useState<InterviewAttempt | null>(null);
  const [answer, setAnswer] = useState('');
  const [feedback, setFeedback] = useState<InterviewFeedback | null>(null);
  const [hintLevel, setHintLevel] = useState(0);
  const [hintText, setHintText] = useState<string | null>(null);
  const [cards, setCards] = useState<InterviewReviewCard[]>([]);
  const [topics, setTopics] = useState<string[]>([]);
  const [customTopic, setCustomTopic] = useState('');
  const [hasResumeClaims, setHasResumeClaims] = useState(false);
  const [progress, setProgress] = useState<InterviewTrainingProgress | null>(null);
  const [comicLightbox, setComicLightbox] = useState<{ src: string; alt: string } | null>(null);
  const [resumeEligibility, setResumeEligibility] = useState<ResumeEligibility | null>(null);
  const [resumeMarkdown, setResumeMarkdown] = useState('');
  const [resumeOpen, setResumeOpen] = useState(false);
  const [resumeBusy, setResumeBusy] = useState(false);
  const [resumeWarn, setResumeWarn] = useState<string[] | null>(null);
  const [targetDeadline, setTargetDeadline] = useState('');
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushTime, setPushTime] = useState('21:00');
  const [pushFrequency, setPushFrequency] = useState<PushFrequency>('weekdays');
  const [pushSettings, setPushSettings] = useState<InterviewPushSettings | null>(null);
  const [pushSettingsBusy, setPushSettingsBusy] = useState(false);
  const [todayPlan, setTodayPlan] = useState<InterviewTodayPlan | null>(null);
  const [todayPlanLoading, setTodayPlanLoading] = useState(false);
  const [learnDialogOpen, setLearnDialogOpen] = useState(false);
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [pushNowBusy, setPushNowBusy] = useState(false);
  const [leftRailOpen, setLeftRailOpen] = useState(true);
  const [rightRailOpen, setRightRailOpen] = useState(true);
  const [atlasExtrasOpen, setAtlasExtrasOpen] = useState(false);
  const [mobileLeftTab, setMobileLeftTab] = useState<'progress' | 'atlas'>('progress');
  const [mobileComicCollapsed, setMobileComicCollapsed] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [draftRole, setDraftRole] = useState('全栈');
  const [draftCustomRole, setDraftCustomRole] = useState('');
  const [draftDifficulty, setDraftDifficulty] = useState<Difficulty>('中级');
  const [draftSalary, setDraftSalary] = useState('25-40k');
  const [draftDeadline, setDraftDeadline] = useState('');
  const [goalConfirmOpen, setGoalConfirmOpen] = useState(false);
  const [deadlineConfirmOpen, setDeadlineConfirmOpen] = useState(false);
  const [switchConfirmOpen, setSwitchConfirmOpen] = useState(false);
  const recentQuestionsRef = useRef<string[]>([]);
  const layoutTier = useTrainLayoutTier();
  const isWideLayout = layoutTier !== 'narrow';
  const isCompactLayout = layoutTier === 'medium';

  const resolvedRole = customRole.trim() || targetRole;
  const training = attempt;
  const ctaKind = attemptCtaKind(attempt?.status);

  useEffect(() => {
    if (layoutTier === 'wide') {
      setLeftRailOpen(true);
      setRightRailOpen(true);
    } else if (layoutTier === 'medium') {
      // Keep practice column dominant: progress open, feedback on demand
      setLeftRailOpen(true);
      setRightRailOpen(false);
    } else {
      setLeftRailOpen(false);
      setRightRailOpen(false);
    }
  }, [layoutTier]);

  useInterviewPush(pushSettings, phase === 'train');

  const refreshTodayPlan = async (opts?: { refresh?: boolean }) => {
    setTodayPlanLoading(true);
    try {
      setTodayPlan(await getInterviewTodayPlan({ refresh: opts?.refresh }));
    } catch {
      // non-blocking
    } finally {
      setTodayPlanLoading(false);
    }
  };

  const openTodayLearning = (opts?: { refresh?: boolean }) => {
    setLeftRailOpen(false);
    void refreshTodayPlan(opts);
    setLearnDialogOpen(true);
  };

  const openHistoryLearning = () => {
    setLeftRailOpen(false);
    setHistoryDialogOpen(true);
  };

  const onPushNow = async () => {
    setPushNowBusy(true);
    setError(null);
    setWarning(null);
    try {
      // Force-refresh so push opens the new Q&A learning sheet.
      await refreshTodayPlan({ refresh: true });
      const result = await pushInterviewNow({
        push_enabled: true,
        push_time: pushTime,
        push_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        push_frequency: pushFrequency,
        target_deadline: targetDeadline || pushSettings?.target_deadline || null,
        last_push_date: pushSettings?.last_push_date || null,
      });
      if (result.ok) {
        setWarning('已推送。系统通知是入口，完整「讲解+题目+答案」在今日学习讲义里');
        setLearnDialogOpen(true);
      } else {
        setError(result.reason || '立即推送失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '立即推送失败');
    } finally {
      setPushNowBusy(false);
    }
  };

  useEffect(() => {
    const hash = window.location.hash || '';
    if (hash.includes('openLearn=1')) {
      setLearnDialogOpen(true);
      void refreshTodayPlan();
      const cleaned = hash.replace(/[?&]openLearn=1/, '').replace(/\?$/, '');
      window.location.hash = cleaned || '#/interview';
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshProgress = async () => {
    try {
      setProgress(await getInterviewTrainingProgress());
    } catch {
      // non-blocking
    }
    try {
      setResumeEligibility(await getResumeEligibility());
    } catch {
      // non-blocking
    }
    void refreshTodayPlan();
  };

  const applyAttempt = (next: InterviewAttempt, opts?: { clearAnswer?: boolean }) => {
    setAttempt(next);
    setLevel(next.level);
    setFeedback(next.evaluation);
    setHintLevel(next.hint_level || 0);
    if (next.question) {
      const prev = recentQuestionsRef.current.filter((q) => q !== next.question);
      recentQuestionsRef.current = [...prev, next.question].slice(-8);
    }
    if (opts?.clearAnswer) {
      setAnswer('');
      setHintText(null);
    } else if (next.status === 'evaluated') {
      setAnswer('');
    } else if (next.status === 'open' || next.status === 'degraded') {
      const latest = [...(next.answers || [])].sort((a, b) => a.version - b.version).at(-1);
      setAnswer(latest?.text ?? '');
    } else if (next.status === 'reanswered') {
      const v2 = next.answers.find((a) => a.version === 2);
      setAnswer(v2?.text ?? '');
    }
    if (next.starter_topics?.length) {
      setTopics((prev) => {
        const merged = [...prev.filter((t) => !next.starter_topics!.includes(t)), ...next.starter_topics!];
        return merged.length ? merged : next.starter_topics!;
      });
    }
  };

  const goalStillMatches = (active: InterviewAttempt) => {
    const snap = active.goal_snapshot || {};
    const snapRole = (snap.target_role || '').trim();
    const role = resolvedRole.trim();
    if (snapRole && role && snapRole !== role) return false;

    const snapLevelRaw = (snap.target_level || '').trim();
    const normLevel = (v: string) =>
      v === 'P5' ? '初级' : v === 'P6' ? '中级' : v === 'P7' ? '高级' : v;
    const snapLevel = normLevel(snapLevelRaw);
    const currentLevel = normLevel(difficulty);
    if (snapLevel && currentLevel && snapLevel !== currentLevel) return false;

    const snapSalary = (snap.salary_band || '').trim();
    if (snapSalary && salaryBand && snapSalary !== salaryBand) return false;
    return true;
  };

  const enterTrain = async (
    nextLevel?: Level,
    topic?: string,
    mode: 'standard' | 'project_sim' = 'standard',
  ) => {
    const useLevel = nextLevel ?? level;
    const active = await getActiveInterviewAttempt();
    if (
      active &&
      mode === 'standard' &&
      (!topic || active.topic === topic) &&
      (active.training_mode ?? 'standard') !== 'project_sim' &&
      goalStillMatches(active)
    ) {
      applyAttempt(active);
      const [review, claims] = await Promise.all([listReviewCards(), listInterviewClaims()]);
      const confirmed = claims.filter((c) => c.status === 'confirmed');
      setHasResumeClaims(confirmed.length > 0);
      const starters = active.starter_topics?.length ? active.starter_topics : [];
      const resumeTopics = confirmed.map((c) => c.label);
      setTopics(
        resumeTopics.length
          ? [...resumeTopics, ...starters.filter((t) => !resumeTopics.includes(t))]
          : starters,
      );
      setCards(review);
      setPhase('train');
      void refreshProgress();
      return;
    }
    if (active) {
      await abandonInterviewAttempt(active.id, 'switch_topic');
    }
    const next = await createInterviewAttempt({ level: useLevel, topic, mode });
    applyAttempt(next, { clearAnswer: true });
    const [review, claims] = await Promise.all([listReviewCards(), listInterviewClaims()]);
    const confirmed = claims.filter((c) => c.status === 'confirmed');
    setHasResumeClaims(confirmed.length > 0);
    const starters = next.starter_topics?.length ? next.starter_topics : [];
    const resumeTopics = confirmed.map((c) => c.label);
    setTopics(
      resumeTopics.length
        ? [...resumeTopics, ...starters.filter((t) => !resumeTopics.includes(t))]
        : starters,
    );
    setCards(review);
    setPhase('train');
    void refreshProgress();
  };

  const boot = async () => {
    setError(null);
    try {
      const profile = await getInterviewProfile();
      if (profile.target_role) setTargetRole(profile.target_role);
      if (profile.target_level) {
        const d = levelToDifficulty(profile.target_level);
        setDifficulty(d);
        setLevel(difficultyToLevel(d));
      }
      if (profile.salary_band) setSalaryBand(profile.salary_band);
      if (profile.target_deadline) setTargetDeadline(profile.target_deadline);

      try {
        const settings = await getInterviewPushSettings();
        setPushSettings(settings);
        setPushEnabled(settings.push_enabled);
        setPushTime(normalizePushTime(settings.push_time || '21:00'));
        setPushFrequency(settings.push_frequency || 'weekdays');
        if (settings.target_deadline && !profile.target_deadline) {
          setTargetDeadline(settings.target_deadline);
        }
      } catch {
        // non-blocking
      }

      if (profile.target_role && profile.target_level && profile.salary_band) {
        await enterTrain(difficultyToLevel(levelToDifficulty(profile.target_level)));
      } else {
        setPhase('setup');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
      setPhase('setup');
    }
  };

  useEffect(() => {
    void boot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!comicLightbox) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setComicLightbox(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [comicLightbox]);

  const normalizePushTime = (raw: string) => {
    const match = raw.trim().match(/^(\d{1,2}):(\d{2})/);
    if (!match) return '21:00';
    const hour = Math.min(23, Math.max(0, Number(match[1])));
    const minute = Math.min(59, Math.max(0, Number(match[2])));
    return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
  };

  const persistPushSettings = async (patch?: {
    push_enabled?: boolean;
    push_time?: string;
    push_frequency?: PushFrequency;
  }) => {
    if (!platform.push.supportsPush) return;
    const nextEnabled = patch?.push_enabled ?? pushEnabled;
    const nextTime = normalizePushTime(patch?.push_time ?? pushTime);
    const nextFrequency = patch?.push_frequency ?? pushFrequency;
    setPushSettingsBusy(true);
    try {
      const settings = await updateInterviewPushSettings({
        push_enabled: nextEnabled,
        push_time: nextTime,
        push_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        push_frequency: nextFrequency,
      });
      setPushSettings(settings);
      setPushEnabled(settings.push_enabled);
      setPushTime(normalizePushTime(settings.push_time || nextTime));
      setPushFrequency(settings.push_frequency || nextFrequency);
      if (settings.push_enabled) {
        const perm = await requestInterviewPushPermission();
        if (perm === 'denied') {
          setWarning('桌面通知被拒绝，你仍可在应用内查看今日计划');
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存推送设置失败');
    } finally {
      setPushSettingsBusy(false);
    }
  };

  const startWithGoal = async () => {
    if (!resolvedRole.trim() || !salaryBand) return;
    setBusy(true);
    setError(null);
    try {
      const nextLevel = difficultyToLevel(difficulty);
      setLevel(nextLevel);
      await updateInterviewProfile({
        target_role: resolvedRole.trim(),
        target_level: difficulty,
        salary_band: salaryBand,
        target_deadline: targetDeadline || null,
      });
      await persistPushSettings({
        push_enabled: platform.push.supportsPush ? pushEnabled : false,
        push_time: pushTime,
        push_frequency: pushFrequency,
      });
      await enterTrain(nextLevel);
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成题目失败');
    } finally {
      setBusy(false);
    }
  };

  const onUpload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const result = await extractResume(file);
      setCandidates(result.claims);
      setWarning(result.warning);
      setPhase('confirm');
    } catch (err) {
      setError(err instanceof Error ? err.message : '解析失败');
    } finally {
      setBusy(false);
    }
  };

  const removeCandidate = (index: number) => {
    setCandidates((prev) => prev.filter((_, i) => i !== index));
  };

  const confirmResumeEnrichment = async () => {
    if (!candidates.length) return;
    setBusy(true);
    setError(null);
    try {
      // Keep existing goal; resume only adds experience/skills.
      await updateInterviewProfile({
        target_role: resolvedRole.trim(),
        target_level: difficulty,
        salary_band: salaryBand,
        keywords: candidates.map((c) => c.label),
      });
      const saved = await Promise.all(candidates.map((c) => saveInterviewClaim(c)));
      await Promise.all(saved.map((c) => confirmInterviewClaim(c.id)));
      setHasResumeClaims(true);
      await enterTrain(level);
    } catch (err) {
      setError(err instanceof Error ? err.message : '确认失败');
    } finally {
      setBusy(false);
    }
  };

  const loadTraining = async (opts?: {
    topic?: string;
    level?: Level;
    exclude_questions?: string[];
    exclude_topics?: string[];
    abandon_reason?: 'skip_retry' | 'switch_topic' | 'change_question';
    mode?: 'standard' | 'project_sim';
  }) => {
    setBusy('loading');
    setError(null);
    try {
      const nextLevel = opts?.level ?? level;
      if (attempt && attempt.status !== 'committed' && attempt.status !== 'abandoned') {
        await abandonInterviewAttempt(attempt.id, opts?.abandon_reason ?? 'switch_topic');
      }
      const next = await createInterviewAttempt({
        level: nextLevel,
        topic: opts?.topic,
        exclude_questions: opts?.exclude_questions,
        exclude_topics: opts?.exclude_topics,
        mode: opts?.mode ?? 'standard',
      });
      applyAttempt(next, { clearAnswer: true });
      setCards(await listReviewCards());
      await refreshProgress();
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取题目失败');
    } finally {
      setBusy(false);
    }
  };

  const changeQuestion = async () => {
    // 换一题 = 同主题换下一道；左侧 tab 才是换分类
    const currentTopic = attempt?.topic ?? training?.topic;
    const exclude = [...recentQuestionsRef.current];
    if (attempt?.question && !exclude.includes(attempt.question)) {
      exclude.push(attempt.question);
    }
    await loadTraining({
      level,
      topic: currentTopic,
      exclude_questions: exclude,
      abandon_reason: 'change_question',
    });
  };

  const resolvedDraftRole = () => (draftCustomRole.trim() || draftRole).trim();

  const savedGoalCore = (): GoalCore => ({
    targetRole: resolvedRole.trim(),
    difficulty,
    salaryBand,
  });

  const draftGoalCore = (): GoalCore => ({
    targetRole: resolvedDraftRole(),
    difficulty: draftDifficulty,
    salaryBand: draftSalary,
  });

  const seedSettingsDrafts = () => {
    setDraftRole(targetRole);
    setDraftCustomRole(customRole);
    setDraftDifficulty(difficulty);
    setDraftSalary(salaryBand);
    setDraftDeadline(targetDeadline || '');
  };

  const openSettings = () => {
    seedSettingsDrafts();
    setSettingsOpen(true);
  };

  const handleSettingsOpenChange = (open: boolean) => {
    setSettingsOpen(open);
    if (!open) {
      setGoalConfirmOpen(false);
      setDeadlineConfirmOpen(false);
    }
  };

  const applySavedGoalFromDraft = () => {
    if (draftCustomRole.trim()) {
      setCustomRole(draftCustomRole.trim());
    } else {
      setCustomRole('');
      setTargetRole(draftRole);
    }
    setDifficulty(draftDifficulty);
    setSalaryBand(draftSalary);
    setLevel(difficultyToLevel(draftDifficulty));
  };

  const persistGoalAndMaybeStart = async (opts: { switchQuestion: boolean }) => {
    const role = resolvedDraftRole();
    if (!role || !draftSalary) return;
    setBusy('loading');
    setError(null);
    try {
      const nextLevel = difficultyToLevel(draftDifficulty);
      await updateInterviewProfile({
        target_role: role,
        target_level: draftDifficulty,
        salary_band: draftSalary,
      });
      applySavedGoalFromDraft();
      setGoalConfirmOpen(false);
      setSettingsOpen(false);
      if (opts.switchQuestion) {
        if (attempt && attemptCtaKind(attempt.status) === 'switch') {
          try {
            await abandonInterviewAttempt(attempt.id, 'switch_topic');
          } catch {
            // 409 terminal ok
          }
        }
        setAttempt(null);
        setFeedback(null);
        setAnswer('');
        setHintText(null);
        recentQuestionsRef.current = [];
        await enterTrain(nextLevel);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存目标失败');
    } finally {
      setBusy(false);
    }
  };

  const onApplyGoal = () => {
    if (!resolvedDraftRole() || !draftSalary) return;
    if (!goalCoreChanged(savedGoalCore(), draftGoalCore())) {
      setSettingsOpen(false);
      return;
    }
    if (attemptCtaKind(attempt?.status) === 'switch') {
      setGoalConfirmOpen(true);
      return;
    }
    void persistGoalAndMaybeStart({ switchQuestion: false });
  };

  const cancelApplyGoal = () => {
    seedSettingsDrafts();
    setGoalConfirmOpen(false);
  };

  const onApplyDeadline = () => {
    const next = draftDeadline || '';
    const saved = targetDeadline || '';
    if (next === saved) return;
    setDeadlineConfirmOpen(true);
  };

  const confirmDeadline = async () => {
    setBusy('loading');
    setError(null);
    try {
      const next = draftDeadline || null;
      await updateInterviewProfile({ target_deadline: next });
      setTargetDeadline(next || '');
      setDeadlineConfirmOpen(false);
      void refreshTodayPlan({ refresh: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存截止日期失败');
    } finally {
      setBusy(false);
    }
  };

  const cancelDeadline = () => {
    setDraftDeadline(targetDeadline || '');
    setDeadlineConfirmOpen(false);
  };

  const onHeaderQuestionCta = async () => {
    if (ctaKind === 'switch') {
      setSwitchConfirmOpen(true);
      return;
    }
    setBusy('loading');
    setError(null);
    try {
      await enterTrain(level);
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成题目失败');
    } finally {
      setBusy(false);
    }
  };

  const confirmSwitchQuestion = async () => {
    setSwitchConfirmOpen(false);
    await changeQuestion();
  };

  const submitAnswer = async (textOverride?: string) => {
    if (!attempt) return;
    const text = (textOverride ?? answer).trim();
    if (!text) return;
    if (attempt.status === 'reanswered' || attempt.status === 'committed') return;
    setBusy('submitting');
    setError(null);
    setWarning(null);
    try {
      const version: 1 | 2 = attempt.status === 'evaluated' ? 2 : 1;
      const result = await submitInterviewAttemptAnswer(attempt.id, {
        text,
        version,
      });
      applyAttempt(result.attempt, { clearAnswer: version === 1 && !result.attempt.evaluation?.complete });
      if (result.degraded) {
        setWarning('评估暂时不可用，答案已保存。可重试提交或跳过本题。');
      }
      if (version === 1 && result.attempt.status === 'evaluated') {
        setAnswer('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '评估失败');
    } finally {
      setBusy(false);
    }
  };

  const requestHint = async () => {
    if (!attempt) return;
    // After L4, allow re-fetching L4 (fresh wording) instead of locking the button forever —
    // especially important after refresh when attempt.hint_level is already 4.
    const next = hintLevel >= 4 ? 4 : Math.min(hintLevel + 1, 4);
    setBusy('hinting');
    setError(null);
    try {
      const hint = await getInterviewAttemptHint(attempt.id, next);
      setHintLevel(next);
      setHintText(hint.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取提示失败');
    } finally {
      setBusy(false);
    }
  };

  const finishRound = async () => {
    if (!attempt) return;
    setBusy('committing');
    try {
      await commitInterviewAttempt(attempt.id);
      await loadTraining({ level });
      await refreshProgress();
    } catch (err) {
      setError(err instanceof Error ? err.message : '完成闭环失败');
      setBusy(false);
    }
  };

  const onCraftResume = async () => {
    setResumeBusy(true);
    setError(null);
    try {
      const result = await craftInterviewResume();
      setResumeMarkdown(result.markdown);
      setResumeWarn(result.warnings.length ? result.warnings : null);
      setResumeOpen(true);
      setResumeEligibility(await getResumeEligibility());
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        const detail = err.detail as unknown;
        const reasons =
          typeof detail === 'object' &&
          detail !== null &&
          'reasons' in detail &&
          Array.isArray((detail as { reasons: unknown }).reasons)
            ? ((detail as { reasons: string[] }).reasons)
            : resumeEligibility?.reasons;
        setError(reasons?.length ? reasons.join('；') : '暂不符合生成简历条件');
      } else {
        setError(err instanceof Error ? err.message : '生成简历失败');
      }
    } finally {
      setResumeBusy(false);
    }
  };

  const skipRetry = async () => {
    if (!attempt) return;
    setBusy('loading');
    try {
      await abandonInterviewAttempt(attempt.id, 'skip_retry');
      await loadTraining({ level });
    } catch (err) {
      setError(err instanceof Error ? err.message : '跳过失败');
      setBusy(false);
    }
  };

  if (phase === 'loading') {
    return (
      <main className="relative flex flex-1 items-center justify-center bg-[var(--bg-main)]">
        <div className="absolute left-3 top-3">
          <SidebarToggle isSidebarOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
        </div>
        <Loader2 className="h-6 w-6 animate-spin text-[var(--text-secondary)]" />
      </main>
    );
  }

  if (phase === 'setup' || phase === 'import' || phase === 'confirm') {
    return (
      <>
      <main className="relative flex-1 overflow-y-auto bg-[var(--bg-main)]">
        <div className="absolute left-3 top-3 z-10">
          <SidebarToggle isSidebarOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
        </div>
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              'linear-gradient(to right, var(--border-color) 1px, transparent 1px), linear-gradient(to bottom, var(--border-color) 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
        />
        <div className="relative mx-auto max-w-3xl px-4 pb-10 pt-16 sm:px-6 md:py-16 md:pt-16">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-600">Interview Navigator</p>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-3xl md:text-4xl">
            {phase === 'confirm'
              ? '确认简历里的经历'
              : phase === 'import'
                ? '可选：补充简历经历'
                : '先定目标，再出题'}
          </h1>
          <p className="mt-3 max-w-xl text-[var(--text-secondary)]">
            {phase === 'confirm'
              ? '简历只补充工作/项目/技术事实。岗位、难度、薪资仍以你刚才设定的目标为准。'
              : phase === 'import'
                ? '上传后可多练项目与工作经历题；不上传也能按岗位目标继续练。'
                : '选择或输入目标岗位、难度与薪资区间，系统据此生成面试题。简历是可选增强。'}
          </p>

          {error && (
            <p className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-600">
              {error}
            </p>
          )}

          {phase === 'setup' && (
            <div className="mt-10 space-y-8">
              <ChoiceGroup label="目标岗位">
                {ROLE_OPTIONS.map((role) => (
                  <ChoiceButton
                    key={role}
                    active={!customRole && targetRole === role}
                    onClick={() => {
                      setCustomRole('');
                      setTargetRole(role);
                    }}
                  >
                    {role}
                  </ChoiceButton>
                ))}
              </ChoiceGroup>
              <input
                value={customRole}
                onChange={(e) => setCustomRole(e.target.value)}
                placeholder="或输入具体岗位，如「资深前端 / AI 全栈」"
                className="w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] px-4 py-3 text-sm text-[var(--text-primary)] outline-none focus:border-amber-500/50"
              />

              <ChoiceGroup label="难度">
                {DIFFICULTY_OPTIONS.map((opt) => (
                  <ChoiceButton
                    key={opt.label}
                    active={difficulty === opt.label}
                    onClick={() => {
                      setDifficulty(opt.label);
                      setLevel(opt.level);
                    }}
                  >
                    {opt.label}
                    <span className="ml-1 opacity-60">· {opt.desc}</span>
                  </ChoiceButton>
                ))}
              </ChoiceGroup>

              <ChoiceGroup label="薪资区间">
                {SALARY_OPTIONS.map((band) => (
                  <ChoiceButton key={band} active={salaryBand === band} onClick={() => setSalaryBand(band)}>
                    {band}
                  </ChoiceButton>
                ))}
              </ChoiceGroup>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-sm font-medium text-[var(--text-primary)]">目标达成时间</p>
                  <input
                    type="date"
                    value={targetDeadline}
                    min={new Date().toISOString().slice(0, 10)}
                    onChange={(e) => setTargetDeadline(e.target.value)}
                    className="mt-3 w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] px-4 py-3 text-sm text-[var(--text-primary)] outline-none focus:border-amber-500/50"
                  />
                  <p className="mt-2 text-[11px] text-[var(--text-secondary)]">
                    系统会按剩余天数倒排学习路线
                    {platform.push.supportsPush ? '，并在设定时间推送今日任务' : ''}
                  </p>
                </div>
                {platform.push.supportsPush ? (
                  <div>
                    <p className="text-sm font-medium text-[var(--text-primary)]">学习提醒</p>
                    <label className="mt-3 flex items-center gap-2 text-sm text-[var(--text-primary)]">
                      <input
                        type="checkbox"
                        checked={pushEnabled}
                        disabled={pushSettingsBusy}
                        onChange={(e) => {
                          const enabled = e.target.checked;
                          setPushEnabled(enabled);
                          void persistPushSettings({ push_enabled: enabled });
                        }}
                        className="rounded border-[var(--border-color)]"
                      />
                      开启桌面提醒
                    </label>
                    <select
                      value={pushFrequency}
                      disabled={pushSettingsBusy}
                      onChange={(e) => {
                        const frequency = e.target.value as PushFrequency;
                        setPushFrequency(frequency);
                        void persistPushSettings({ push_frequency: frequency });
                      }}
                      className="mt-3 w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] px-4 py-3 text-sm text-[var(--text-primary)] outline-none focus:border-amber-500/50 disabled:opacity-50"
                    >
                      {PUSH_FREQUENCY_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    <input
                      type="time"
                      value={pushTime}
                      disabled={pushSettingsBusy}
                      onChange={(e) => {
                        const next = normalizePushTime(e.target.value);
                        setPushTime(next);
                        void persistPushSettings({ push_time: next });
                      }}
                      className="mt-3 w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] px-4 py-3 text-sm text-[var(--text-primary)] outline-none focus:border-amber-500/50 disabled:opacity-50"
                    />
                    <button
                      type="button"
                      disabled={pushNowBusy || !targetDeadline}
                      onClick={() => void onPushNow()}
                      className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-sm font-medium text-amber-900 hover:bg-amber-500/20 disabled:opacity-50 dark:text-amber-100"
                    >
                      {pushNowBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}
                      立即推送
                    </button>
                    <p className="mt-2 text-[11px] text-[var(--text-secondary)]">
                      改完开关/频率/时间会自动保存；也可用「立即推送」预览效果
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm font-medium text-[var(--text-primary)]">学习提醒</p>
                    <p className="mt-3 rounded-xl border border-dashed border-[var(--border-color)] px-4 py-3 text-[11px] leading-relaxed text-[var(--text-secondary)]">
                      定时推送为桌面端能力。Web 端可用「立即推送」预览浏览器通知效果。
                    </p>
                    <button
                      type="button"
                      disabled={pushNowBusy || !targetDeadline}
                      onClick={() => void onPushNow()}
                      className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-sm font-medium text-amber-900 hover:bg-amber-500/20 disabled:opacity-50 dark:text-amber-100"
                    >
                      {pushNowBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}
                      立即推送
                    </button>
                  </div>
                )}
              </div>

              <div className="flex flex-col gap-3 pt-2 sm:flex-row sm:flex-wrap">
                <button
                  type="button"
                  disabled={busy || !resolvedRole.trim() || !salaryBand}
                  onClick={() => void startWithGoal()}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-amber-600 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50 sm:w-auto"
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                  生成面试题并开始
                </button>
                <button
                  type="button"
                  disabled={busy || !resolvedRole.trim() || !salaryBand}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await updateInterviewProfile({
                        target_role: resolvedRole.trim(),
                        target_level: difficulty,
                        salary_band: salaryBand,
                      });
                      setLevel(difficultyToLevel(difficulty));
                      setPhase('import');
                    } catch (err) {
                      setError(err instanceof Error ? err.message : '保存目标失败');
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="w-full rounded-xl border border-[var(--border-color)] px-5 py-2.5 text-sm text-[var(--text-secondary)] disabled:opacity-50 sm:w-auto"
                >
                  先导入简历再出题
                </button>
                {targetDeadline && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      void (async () => {
                        setBusy(true);
                        try {
                          await updateInterviewProfile({
                            target_role: resolvedRole.trim(),
                            target_level: difficulty,
                            salary_band: salaryBand,
                            target_deadline: targetDeadline,
                          });
                          await refreshTodayPlan();
                          setLearnDialogOpen(true);
                        } catch (err) {
                          setError(err instanceof Error ? err.message : '加载今日学习失败');
                        } finally {
                          setBusy(false);
                        }
                      })();
                    }}
                    className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-amber-500/40 bg-amber-500/10 px-5 py-2.5 text-sm text-amber-900 disabled:opacity-50 dark:text-amber-100 sm:w-auto"
                  >
                    <BookOpen className="h-4 w-4" />
                    今日学习文档
                  </button>
                )}
              </div>
            </div>
          )}

          {phase === 'import' && (
            <div className="mt-10 space-y-4">
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void onUpload(file);
                }}
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
                className="group flex w-full flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--border-color)] bg-[var(--bg-card)] px-6 py-12 transition hover:border-amber-500/50"
              >
                {busy ? (
                  <Loader2 className="h-7 w-7 animate-spin text-amber-600" />
                ) : (
                  <FileUp className="h-7 w-7 text-[var(--text-secondary)] transition group-hover:text-amber-600" />
                )}
                <span className="mt-3 text-sm font-medium text-[var(--text-primary)]">上传 PDF / DOCX 简历</span>
                <span className="mt-1 text-xs text-[var(--text-secondary)]">
                  读取技术、工作与项目经历；岗位/难度/薪资沿用你的目标设定
                </span>
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void startWithGoal()}
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-amber-600 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                跳过简历，按目标直接出题
              </button>
              <button
                type="button"
                onClick={() => setPhase('setup')}
                className="w-full text-center text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                返回修改目标
              </button>
            </div>
          )}

          {phase === 'confirm' && (
            <div className="mt-10 space-y-8">
              {warning && (
                <p className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {warning}
                </p>
              )}
              <p className="text-sm text-[var(--text-secondary)]">
                当前目标：{resolvedRole} · {difficulty} · {salaryBand}
              </p>
              {(['skill', 'project', 'role'] as const).map((category) => {
                const items = candidates
                  .map((item, index) => ({ item, index }))
                  .filter(({ item }) => item.category === category);
                if (!items.length) return null;
                return (
                  <div key={category}>
                    <p className="text-sm font-medium text-[var(--text-primary)]">{CATEGORY_LABEL[category]}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {items.map(({ item, index }) => (
                        <span
                          key={`${item.label}-${index}`}
                          className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-1.5 text-sm text-[var(--text-primary)]"
                        >
                          {item.label}
                          <button
                            type="button"
                            aria-label={`删除 ${item.label}`}
                            onClick={() => removeCandidate(index)}
                            className="text-[var(--text-secondary)] hover:text-red-500"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={busy || !candidates.length}
                  onClick={() => void confirmResumeEnrichment()}
                  className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                  确认经历并生成题目
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCandidates([]);
                    setPhase('import');
                  }}
                  className="rounded-xl border border-[var(--border-color)] px-5 py-2.5 text-sm text-[var(--text-secondary)]"
                >
                  重新上传
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
      <TodayLearningDialog
        open={learnDialogOpen}
        onOpenChange={setLearnDialogOpen}
        todayPlan={todayPlan}
        loading={todayPlanLoading}
        onRefresh={() => void refreshTodayPlan({ refresh: true })}
        onStatusChange={() => void refreshTodayPlan()}
      />
      <HistoryLearningDialog
        open={historyDialogOpen}
        onOpenChange={setHistoryDialogOpen}
      />
    </>
    );
  }

  const covered = feedback?.covered_nodes ?? [];
  const missing = feedback?.missing_nodes ?? training?.missing_nodes ?? [];
  const focus = feedback?.breakpoint ?? training?.focus_node;
  const snap = training?.goal_snapshot;
  const goalLine = [
    snap?.target_role || resolvedRole,
    snap?.target_level || difficulty,
    snap?.salary_band || salaryBand,
  ]
    .filter(Boolean)
    .join(' · ');
  const canSubmitV1 = attempt && ['open', 'degraded'].includes(attempt.status);
  const canSubmitV2 = attempt?.status === 'evaluated';
  const canCommit =
    attempt &&
    (attempt.status === 'reanswered' ||
      (attempt.status === 'evaluated' && attempt.evaluation?.complete));
  const showSkip =
    !!attempt &&
    (attempt.status === 'degraded' ||
      (attempt.status === 'evaluated' && !attempt.evaluation?.complete));

  return (
    <main className="flex flex-1 flex-col overflow-hidden bg-[var(--bg-main)]">
      <header
        className={cn(
          'flex flex-shrink-0 flex-col border-b border-[var(--border-color)] bg-[var(--bg-card)]',
          isCompactLayout ? 'gap-1.5 px-3 py-2' : 'gap-2 px-3 py-2.5 sm:px-5 sm:py-3',
        )}
      >
        <div className="flex min-w-0 items-center gap-1.5 sm:gap-2">
          <SidebarToggle isSidebarOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
          <Button
            variant="ghost"
            size="icon"
            onClick={() =>
              setLeftRailOpen((v) => {
                const next = !v;
                if (next && isCompactLayout) setRightRailOpen(false);
                return next;
              })
            }
            aria-label={leftRailOpen ? '收起训练进展' : '展开训练进展'}
            title={leftRailOpen ? '收起训练进展' : '展开训练进展'}
            className={cn(
              'h-9 w-9 shrink-0 text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
              leftRailOpen && 'text-amber-700 dark:text-amber-300',
            )}
          >
            <PanelLeft size={18} />
          </Button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-600">
              {goalLine || 'Workbench'} · 约 3 分钟
            </p>
            <h1 className="truncate text-base font-semibold text-[var(--text-primary)] sm:text-lg">
              {training
                ? `${training.training_mode === 'project_sim' ? '项目模拟 · ' : ''}今天练：${training.topic}`
                : '面试导航'}
            </h1>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() =>
              setRightRailOpen((v) => {
                const next = !v;
                if (next && isCompactLayout) setLeftRailOpen(false);
                return next;
              })
            }
            aria-label={rightRailOpen ? '收起反馈面板' : '展开反馈面板'}
            title={rightRailOpen ? '收起反馈面板' : '展开反馈面板'}
            className={cn(
              'h-9 w-9 shrink-0 text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
              rightRailOpen && 'text-amber-700 dark:text-amber-300',
            )}
          >
            <PanelRight size={18} />
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
          <div className="flex shrink-0 items-center gap-0.5 rounded-lg border border-[var(--border-color)] p-0.5 sm:gap-1 sm:p-1">
            {DIFFICULTY_OPTIONS.map((opt) => (
              <button
                key={opt.label}
                type="button"
                onClick={() => {
                  setDifficulty(opt.label);
                  setLevel(opt.level);
                  void (async () => {
                    await updateInterviewProfile({
                      target_role: resolvedRole.trim(),
                      target_level: opt.label,
                      salary_band: salaryBand,
                    });
                    await loadTraining({ level: opt.level, topic: training?.topic });
                  })();
                }}
                className={`rounded-md px-2 py-1 text-xs sm:px-2.5 ${
                  difficulty === opt.label
                    ? 'bg-amber-500/15 font-semibold text-amber-700 dark:text-amber-300'
                    : 'text-[var(--text-secondary)]'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <TodayLearningHeaderButton
            todayPlan={todayPlan}
            loading={todayPlanLoading}
            onClick={openTodayLearning}
          />
          <HistoryLearningHeaderButton onClick={openHistoryLearning} />
          <button
            type="button"
            disabled={pushNowBusy}
            onClick={() => void onPushNow()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/40 bg-amber-500/10 px-2.5 py-1.5 text-sm font-medium text-amber-900 hover:bg-amber-500/20 disabled:opacity-50 dark:text-amber-100 sm:px-3"
            title="立即推送今日学习内容"
          >
            {pushNowBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Bell className="h-3.5 w-3.5" />}
            <span className="hidden sm:inline">立即推送</span>
          </button>
          <button
            type="button"
            disabled={!!busy}
            onClick={() => void onHeaderQuestionCta()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-color)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50 sm:px-3"
          >
            {ctaKind === 'switch' ? <SkipForward className="h-3.5 w-3.5" /> : null}
            {ctaKind === 'switch' ? t('interviewNav.switchQuestion') : t('interviewNav.generateQuestion')}
          </button>
          <button
            type="button"
            disabled={!!busy}
            onClick={() => openSettings()}
            className="px-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50 sm:px-0"
          >
            {t('interviewNav.settings')}
          </button>
          <button
            type="button"
            onClick={() => setPhase('import')}
            className="px-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] sm:px-0"
          >
            {hasResumeClaims ? '更新简历' : '补充简历'}
          </button>
          <button
            type="button"
            disabled={!resumeEligibility?.eligible || !!busy || resumeBusy}
            title={
              resumeEligibility && !resumeEligibility.eligible
                ? resumeEligibility.reasons.join('；')
                : '基于已确认事实与训练证据生成 Markdown 简历'
            }
            onClick={() => void onCraftResume()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-color)] px-2.5 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50 sm:px-3"
          >
            {resumeBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            生成简历
          </button>
        </div>
      </header>

      {error && (
        <p className="mx-3 mt-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-600 sm:mx-5">
          {error}
        </p>
      )}
      {warning && (
        <p className="mx-3 mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-800 dark:text-amber-100 sm:mx-5">
          {warning}
        </p>
      )}

      <div
        className={cn(
          'relative flex min-h-0 flex-1 overflow-hidden',
          isCompactLayout ? 'gap-2.5 p-2.5' : 'gap-3 p-3 sm:gap-4 sm:p-4',
        )}
      >
        <TrainSideRail
          open={leftRailOpen}
          onClose={() => setLeftRailOpen(false)}
          side="left"
          isWide={isWideLayout}
          widthClass={isCompactLayout ? 'w-[300px]' : 'w-[280px]'}
          title="训练导航"
          presentation={!isWideLayout ? 'bottom' : 'side'}
        >
          {!isWideLayout ? (
            <div className="space-y-3">
              <div className="sticky top-0 z-10 -mx-1 flex gap-1 rounded-xl border border-[var(--border-color)] bg-[var(--bg-main)] p-1">
                {(
                  [
                    { id: 'progress' as const, label: '进展' },
                    { id: 'atlas' as const, label: '地图' },
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setMobileLeftTab(tab.id)}
                    className={cn(
                      'min-h-10 flex-1 rounded-lg text-sm font-medium transition',
                      mobileLeftTab === tab.id
                        ? 'bg-amber-500/15 text-amber-900 dark:text-amber-100'
                        : 'text-[var(--text-secondary)]',
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
              {mobileLeftTab === 'progress' ? (
                progress ? (
                  <ProgressPanel
                    progress={progress}
                    todayPlan={todayPlan}
                    todayPlanLoading={todayPlanLoading}
                    onOpenTodayLearning={openTodayLearning}
                    onOpenHistoryLearning={openHistoryLearning}
                    onStartModule={(topic) => {
                      setLeftRailOpen(false);
                      void loadTraining({ topic, level });
                    }}
                    onProjectSim={() => {
                      setLeftRailOpen(false);
                      void loadTraining({ mode: 'project_sim', level, topic: 'Agent' });
                    }}
                  />
                ) : (
                  <p className="text-xs text-[var(--text-secondary)]">加载进展中…</p>
                )
              ) : training ? (
                <AtlasRailBody
                  training={training}
                  topics={topics}
                  customTopic={customTopic}
                  setCustomTopic={setCustomTopic}
                  setTopics={setTopics}
                  cards={cards}
                  hasResumeClaims={hasResumeClaims}
                  busy={busy}
                  comicCollapsed={mobileComicCollapsed}
                  onToggleComic={() => setMobileComicCollapsed((v) => !v)}
                  onOpenComic={(src, alt) => {
                    setLeftRailOpen(false);
                    setComicLightbox({ src, alt });
                  }}
                  onPickTopic={(topic) => {
                    if (topic !== training.topic) recentQuestionsRef.current = [];
                    setLeftRailOpen(false);
                    void loadTraining({ topic, level });
                  }}
                />
              ) : (
                <p className="text-xs text-[var(--text-secondary)]">暂无当前练习地图</p>
              )}
            </div>
          ) : isCompactLayout ? (
            <Panel title="训练导航" eyebrow="Progress · Atlas" compact className="h-full min-h-0">
              {progress ? (
                <ProgressPanel
                  progress={progress}
                  todayPlan={todayPlan}
                  todayPlanLoading={todayPlanLoading}
                  dense
                  onOpenTodayLearning={openTodayLearning}
                  onOpenHistoryLearning={openHistoryLearning}
                  onStartModule={(topic) => void loadTraining({ topic, level })}
                  onProjectSim={() => void loadTraining({ mode: 'project_sim', level, topic: 'Agent' })}
                />
              ) : (
                <p className="text-xs text-[var(--text-secondary)]">加载进展中…</p>
              )}
              {training && (
                <div className="mt-4 border-t border-[var(--border-color)] pt-3">
                  <AtlasRailBody
                    training={training}
                    topics={topics}
                    customTopic={customTopic}
                    setCustomTopic={setCustomTopic}
                    setTopics={setTopics}
                    cards={cards}
                    hasResumeClaims={hasResumeClaims}
                    busy={busy}
                    extrasOpen={atlasExtrasOpen}
                    onToggleExtras={() => setAtlasExtrasOpen((v) => !v)}
                    onOpenComic={(src, alt) => setComicLightbox({ src, alt })}
                    onPickTopic={(topic) => {
                      if (topic !== training.topic) recentQuestionsRef.current = [];
                      void loadTraining({ topic, level });
                    }}
                    compactExtras
                  />
                </div>
              )}
            </Panel>
          ) : (
            <>
              <Panel title="训练进展" eyebrow="Progress" compact={isCompactLayout}>
                {progress ? (
                  <ProgressPanel
                    progress={progress}
                    todayPlan={todayPlan}
                    todayPlanLoading={todayPlanLoading}
                    onOpenTodayLearning={openTodayLearning}
                    onOpenHistoryLearning={openHistoryLearning}
                    onStartModule={(topic) => void loadTraining({ topic, level })}
                    onProjectSim={() => void loadTraining({ mode: 'project_sim', level, topic: 'Agent' })}
                  />
                ) : (
                  <p className="text-xs text-[var(--text-secondary)]">加载进展中…</p>
                )}
              </Panel>
              <Panel title="面试地图" eyebrow="Atlas" compact={isCompactLayout}>
                {training ? (
                  <AtlasRailBody
                    training={training}
                    topics={topics}
                    customTopic={customTopic}
                    setCustomTopic={setCustomTopic}
                    setTopics={setTopics}
                    cards={cards}
                    hasResumeClaims={hasResumeClaims}
                    busy={busy}
                    onOpenComic={(src, alt) => setComicLightbox({ src, alt })}
                    onPickTopic={(topic) => {
                      if (topic !== training.topic) recentQuestionsRef.current = [];
                      void loadTraining({ topic, level });
                    }}
                  />
                ) : null}
              </Panel>
            </>
          )}
        </TrainSideRail>

        <Panel
          title="当前练习"
          eyebrow="主动回忆"
          compact={isCompactLayout}
          className="min-w-0 flex-1 overflow-hidden"
        >
          {training && (
            <div className="flex h-full flex-col">
              <h3
                className={cn(
                  'font-semibold leading-snug text-[var(--text-primary)]',
                  isCompactLayout ? 'text-base sm:text-lg' : 'text-lg sm:text-xl',
                )}
              >
                {training.question}
              </h3>
              <p
                className={cn(
                  'text-[var(--text-secondary)]',
                  isCompactLayout ? 'mt-1.5 text-xs' : 'mt-2 text-sm',
                )}
              >
                先自己说。重点走通「
                <span className="font-semibold text-amber-700 dark:text-amber-300">
                  {routeNodeLabel(training.focus_node)}
                </span>
                」，不要追求完整范文。
              </p>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder={
                  canSubmitV2
                    ? '针对断点重答一版…'
                    : '开始说吧，短一点也没关系…'
                }
                disabled={attempt?.status === 'committed' || attempt?.status === 'abandoned'}
                className={cn(
                  'w-full flex-1 resize-none rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] text-sm text-[var(--text-primary)] outline-none focus:border-amber-500/50 disabled:opacity-60',
                  isCompactLayout
                    ? 'mt-3 min-h-[120px] p-3 sm:min-h-[140px]'
                    : 'mt-5 min-h-[140px] p-4 sm:min-h-[160px]',
                )}
              />
              {hintText && (
                <p className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-100">
                  <Lightbulb className="mr-1.5 inline h-3.5 w-3.5" />
                  L{hintLevel} · {hintText}
                </p>
              )}
              <div className="mt-4 flex flex-wrap gap-2 pb-[max(0px,env(safe-area-inset-bottom))]">
                {(canSubmitV1 || canSubmitV2) && (
                  <>
                    <VoiceAnswerControls
                      disabled={
                        !!busy ||
                        attempt?.status === 'committed' ||
                        attempt?.status === 'abandoned' ||
                        attempt?.status === 'reanswered'
                      }
                      onError={(message) => setError(message)}
                      onTranscribed={async (text) => {
                        setAnswer(text);
                        const canAuto =
                          !!attempt &&
                          (attempt.status === 'open' ||
                            attempt.status === 'answering' ||
                            attempt.status === 'evaluated' ||
                            attempt.status === 'degraded');
                        if (canAuto) {
                          await submitAnswer(text);
                        } else {
                          setWarning('转写已填入答题框，请手动提交');
                        }
                      }}
                    />
                    <button
                      type="button"
                      disabled={!!busy || !answer.trim()}
                      onClick={() => void submitAnswer()}
                      className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                    >
                      {busy === 'submitting' ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <ArrowRight className="h-4 w-4" />
                      )}
                      {canSubmitV2 ? '提交重答' : '提交并看断点'}
                    </button>
                  </>
                )}
                {canCommit && (
                  <button
                    type="button"
                    disabled={!!busy}
                    onClick={() => void finishRound()}
                    className="inline-flex items-center gap-2 rounded-xl bg-[var(--text-primary)] px-4 py-2 text-sm font-semibold text-[var(--bg-card)] disabled:opacity-50"
                  >
                    {busy === 'committing' ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Check className="h-4 w-4" />
                    )}
                    完成并保存复习卡
                  </button>
                )}
                {showSkip && (
                  <button
                    type="button"
                    disabled={!!busy}
                    onClick={() => void skipRetry()}
                    className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)]"
                  >
                    跳过（不计入闭环）
                  </button>
                )}
                <button
                  type="button"
                  disabled={!!busy || !attempt || attempt.status === 'committed'}
                  title={
                    hintLevel >= 4
                      ? '已到最深层，可再点一次换一版提示'
                      : feedback
                        ? '基于本题与你的答卷给出最小提示'
                        : '卡住了也可以点：先按本题给回忆方向（提交答卷后会更贴你的断点）'
                  }
                  onClick={() => void requestHint()}
                  className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)] disabled:opacity-50"
                >
                  <Lightbulb className="h-4 w-4" />
                  {hintLevel === 0
                    ? '给我提示'
                    : hintLevel >= 4
                      ? '再看提示'
                      : `再深一层 (${hintLevel}/4)`}
                </button>
              </div>
              {attempt?.status === 'degraded' && (
                <p className="mt-3 text-sm text-amber-700 dark:text-amber-200">
                  评估降级：答案已保留。可修改后再次提交，或跳过本题。
                </p>
              )}
            </div>
          )}
        </Panel>

        <TrainSideRail
          open={rightRailOpen}
          onClose={() => setRightRailOpen(false)}
          side="right"
          isWide={isWideLayout}
          widthClass={isCompactLayout ? 'w-[200px]' : 'w-[260px]'}
          title="反馈与下一步"
        >
          {(() => {
            const feedbackBody = training ? (
              <>
                <p className="mb-3 text-[10px] font-medium tracking-wide text-[var(--text-secondary)]">
                  断点提示
                </p>
                <RouteChecklist nodes={training.route_nodes} covered={covered} missing={missing} focus={focus} />
                {feedback ? (
                  <div className="mt-5 space-y-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-main)] p-3 text-sm">
                    <p className="text-[var(--text-primary)]">{feedback.next_step}</p>
                    {feedback.hint && (
                      <p className="text-[var(--text-secondary)]">最小提示：{feedback.hint.recall}</p>
                    )}
                    {attempt?.status === 'evaluated' && !feedback.complete && (
                      <p className="text-xs text-[var(--text-secondary)]">
                        针对断点提交重答后，才能计入闭环并保存复习卡。
                      </p>
                    )}
                    {canCommit && (
                      <button
                        type="button"
                        disabled={!!busy}
                        onClick={() => {
                          setRightRailOpen(false);
                          void finishRound();
                        }}
                        className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-[var(--text-primary)] px-3 py-2 text-sm font-semibold text-[var(--bg-card)] disabled:opacity-50"
                      >
                        完成并保存复习卡
                      </button>
                    )}
                  </div>
                ) : (
                  <p className="mt-5 text-sm text-[var(--text-secondary)]">
                    先作答。提交后会标出已走通节点与当前断点，不会默认给完整答案。
                  </p>
                )}
              </>
            ) : null;

            if (!isWideLayout) return feedbackBody;

            return (
              <Panel
                title="反馈与下一步"
                eyebrow="断点提示"
                compact={isCompactLayout}
                className="h-full min-h-0 overflow-hidden"
              >
                {training && (
                  <>
                    <RouteChecklist
                      nodes={training.route_nodes}
                      covered={covered}
                      missing={missing}
                      focus={focus}
                    />
                    {feedback ? (
                      <div className="mt-5 space-y-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-main)] p-3 text-sm">
                        <p className="text-[var(--text-primary)]">{feedback.next_step}</p>
                        {feedback.hint && (
                          <p className="text-[var(--text-secondary)]">最小提示：{feedback.hint.recall}</p>
                        )}
                        {attempt?.status === 'evaluated' && !feedback.complete && (
                          <p className="text-xs text-[var(--text-secondary)]">
                            针对断点提交重答后，才能计入闭环并保存复习卡。
                          </p>
                        )}
                        {canCommit && (
                          <button
                            type="button"
                            disabled={!!busy}
                            onClick={() => void finishRound()}
                            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--text-primary)] px-3 py-2 text-sm font-semibold text-[var(--bg-card)] disabled:opacity-50"
                          >
                            完成并保存复习卡
                          </button>
                        )}
                      </div>
                    ) : (
                      <p className="mt-5 text-sm text-[var(--text-secondary)]">
                        先作答。提交后会标出已走通节点与当前断点，不会默认给完整答案。
                      </p>
                    )}
                  </>
                )}
              </Panel>
            );
          })()}
        </TrainSideRail>
      </div>

      <Dialog open={resumeOpen} onOpenChange={setResumeOpen}>
        <DialogContent className="max-w-2xl border-[var(--border-color)] bg-[var(--bg-card)]">
          <DialogHeader>
            <DialogTitle className="text-[var(--text-primary)]">生成的简历（Markdown）</DialogTitle>
          </DialogHeader>
          {resumeWarn?.length ? (
            <p className="text-xs text-amber-700 dark:text-amber-300">{resumeWarn.join(' · ')}</p>
          ) : null}
          <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg border border-[var(--border-color)] p-3 text-sm text-[var(--text-primary)]">
            {resumeMarkdown}
          </pre>
          <button
            type="button"
            onClick={() => void navigator.clipboard.writeText(resumeMarkdown)}
            className="inline-flex items-center justify-center rounded-lg border border-[var(--border-color)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            复制
          </button>
        </DialogContent>
      </Dialog>

      <TodayLearningDialog
        open={learnDialogOpen}
        onOpenChange={setLearnDialogOpen}
        todayPlan={todayPlan}
        loading={todayPlanLoading}
        onPractice={(topic) => void loadTraining({ topic, level })}
        onRefresh={() => void refreshTodayPlan({ refresh: true })}
        onStatusChange={() => void refreshTodayPlan()}
      />
      <HistoryLearningDialog
        open={historyDialogOpen}
        onOpenChange={setHistoryDialogOpen}
        onPractice={(topic) => void loadTraining({ topic, level })}
      />

      <InterviewSettingsSheet
        open={settingsOpen}
        onOpenChange={handleSettingsOpenChange}
        targetRole={draftRole}
        customRole={draftCustomRole}
        difficulty={draftDifficulty}
        salaryBand={draftSalary}
        onTargetRole={setDraftRole}
        onCustomRole={setDraftCustomRole}
        onDifficulty={(d) => setDraftDifficulty(d as Difficulty)}
        onSalaryBand={setDraftSalary}
        onApplyGoal={onApplyGoal}
        applyGoalDisabled={!!busy}
        targetDeadline={draftDeadline}
        onTargetDeadline={setDraftDeadline}
        onApplyDeadline={onApplyDeadline}
        applyDeadlineDisabled={!!busy}
        supportsPush={platform.push.supportsPush}
        pushEnabled={pushEnabled}
        pushFrequency={pushFrequency}
        pushTime={pushTime}
        pushSettingsBusy={pushSettingsBusy}
        onPushEnabled={(enabled) => {
          setPushEnabled(enabled);
          void persistPushSettings({ push_enabled: enabled });
        }}
        onPushFrequency={(frequency) => {
          const next = frequency as PushFrequency;
          setPushFrequency(next);
          void persistPushSettings({ push_frequency: next });
        }}
        onPushTime={(time) => {
          const next = normalizePushTime(time);
          setPushTime(next);
          void persistPushSettings({ push_time: next });
        }}
        onPushNow={() => void onPushNow()}
        pushNowBusy={pushNowBusy}
      />

      <AlertDialog
        open={goalConfirmOpen}
        onOpenChange={(open) => {
          if (!open) cancelApplyGoal();
          else setGoalConfirmOpen(true);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('interviewNav.goalChangedTitle')}</AlertDialogTitle>
            <AlertDialogDescription>{t('interviewNav.goalChangedBody')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('interviewNav.applyGoalLater')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                void persistGoalAndMaybeStart({ switchQuestion: true });
              }}
            >
              {t('interviewNav.applyGoalNow')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={deadlineConfirmOpen}
        onOpenChange={(open) => {
          if (!open) cancelDeadline();
          else setDeadlineConfirmOpen(true);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('interviewNav.deadlineTitle')}</AlertDialogTitle>
            <AlertDialogDescription>{t('interviewNav.deadlineBody')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('interviewNav.deadlineCancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                void confirmDeadline();
              }}
            >
              {t('interviewNav.deadlineConfirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={switchConfirmOpen} onOpenChange={setSwitchConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('interviewNav.switchTitle')}</AlertDialogTitle>
            <AlertDialogDescription>{t('interviewNav.switchBody')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('interviewNav.switchCancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={() => void confirmSwitchQuestion()}>
              {t('interviewNav.switchConfirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {comicLightbox && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="漫画大图"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setComicLightbox(null)}
        >
          <button
            type="button"
            className="absolute right-4 top-4 inline-flex h-10 w-10 items-center justify-center rounded-full bg-white/90 text-zinc-900 shadow"
            onClick={() => setComicLightbox(null)}
            aria-label="关闭"
          >
            <X className="h-5 w-5" />
          </button>
          <img
            src={comicLightbox.src}
            alt={comicLightbox.alt}
            className="max-h-[90vh] max-w-[min(960px,95vw)] rounded-lg object-contain shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </main>
  );
}
